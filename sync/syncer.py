"""
syncer.py - 核心同步逻辑
从 GitHub 仓库下载 skill 文件到本地目录
"""

import io
import os
import logging
import shutil
import tarfile
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def get_http_session(token: str | None = None) -> requests.Session:
    """创建配置了 Retry 策略和 Auth Header 的 requests.Session"""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"Accept": "application/vnd.github.v3+json"})
    if token:
        session.headers["Authorization"] = f"token {token}"
    return session


def list_skills(
    source: dict, token: str | None = None, session: requests.Session | None = None
) -> list[str]:
    """
    列出某个来源下的所有 skill 目录名
    返回: ['claude-api', 'frontend-design', ...]
    """
    if session is None:
        session = get_http_session(token)

    repo = source["repo"]
    branch = source.get("branch", "main")
    path = source.get("path", "")

    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    params = {"ref": branch}
    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()

    items = resp.json()
    return [item["name"] for item in items if item["type"] == "dir"]


def filter_skills(all_skills: list[str], source: dict) -> list[str]:
    """
    根据 mode + include/exclude 过滤 skill 列表
    """
    mode = source.get("mode", "exclude")

    if mode == "include":
        include_list = source.get("include", [])
        filtered = [s for s in all_skills if s in include_list]
        missing = set(include_list) - set(all_skills)
        if missing:
            logger.warning(
                "Source [%s]: include 列表中以下 skill 不存在: %s",
                source["name"],
                missing,
            )
        return filtered

    # mode == "exclude"
    exclude_list = source.get("exclude", [])
    return [s for s in all_skills if s not in exclude_list]


def extract_skills_from_tarball(
    tarball_bytes: bytes,
    remote_path: str,
    wanted_skills: list[str],
    source_dir: str,
) -> None:
    """
    从 Tarball 字节流中高效提取需要的 skill 目录到本地
    """
    with tarfile.open(fileobj=io.BytesIO(tarball_bytes), mode="r:gz") as tar:
        members = tar.getmembers()
        if not members:
            return

        # 第一级根目录前缀（例如 "anthropics-skills-a1b2c3d/"）
        first_member = members[0].name
        top_prefix = first_member.split("/")[0] + "/"

        # 拼接 remote_path 前缀
        prefix = top_prefix
        clean_path = remote_path.strip("/")
        if clean_path:
            prefix += clean_path + "/"

        for skill_name in wanted_skills:
            skill_prefix = prefix + skill_name + "/"
            local_skill_path = os.path.join(source_dir, skill_name)

            if os.path.isdir(local_skill_path):
                shutil.rmtree(local_skill_path)
            os.makedirs(local_skill_path, exist_ok=True)

            extracted_count = 0
            for member in members:
                if member.name.startswith(skill_prefix) and member.isfile():
                    rel_path = member.name[len(skill_prefix) :]
                    target_file = os.path.join(local_skill_path, rel_path)
                    os.makedirs(os.path.dirname(target_file), exist_ok=True)

                    extracted_file = tar.extractfile(member)
                    if extracted_file:
                        with open(target_file, "wb") as f:
                            shutil.copyfileobj(extracted_file, f)
                        extracted_count += 1

            logger.info("  解压 skill: %s (%d 个文件)", skill_name, extracted_count)


def sync_source(
    source: dict,
    skills_dir: str,
    token: str | None = None,
    session: requests.Session | None = None,
) -> None:
    """
    同步一个来源的 skill 到本地 skills/<source-name>/ 目录
    """
    if session is None:
        session = get_http_session(token)

    name = source["name"]
    repo = source["repo"]
    branch = source.get("branch", "main")
    path = source.get("path", "")

    source_dir = os.path.join(skills_dir, name)
    logger.info("同步来源 [%s] 从 %s ...", name, repo)

    # 1. 获取远端 skill 列表
    all_skills = list_skills(source, token, session=session)
    logger.info("  远端共 %d 个 skill", len(all_skills))

    # 2. 过滤
    wanted_skills = filter_skills(all_skills, source)
    logger.info("  过滤后保留 %d 个: %s", len(wanted_skills), wanted_skills)

    if not wanted_skills:
        logger.info("  没有需要同步的 skill")
        return

    # 3. 清理：删除本地存在但不再需要的 skill
    if os.path.isdir(source_dir):
        existing = set(os.listdir(source_dir))
        to_remove = existing - set(wanted_skills)
        for skill_name in to_remove:
            remove_path = os.path.join(source_dir, skill_name)
            if os.path.isdir(remove_path):
                logger.info("  删除不再需要的 skill: %s", skill_name)
                shutil.rmtree(remove_path)

    os.makedirs(source_dir, exist_ok=True)

    # 4. 一次性下载 Tarball 并解压提取 wanted_skills
    tarball_url = f"{GITHUB_API}/repos/{repo}/tarball/{branch}"
    logger.info("  正在下载仓库归档文件 (%s)...", tarball_url)
    resp = session.get(tarball_url, timeout=60, allow_redirects=True)
    resp.raise_for_status()

    extract_skills_from_tarball(resp.content, path, wanted_skills, source_dir)
    logger.info("来源 [%s] 同步完成 ✓", name)


def build_favorites(favorites: list[dict], skills_dir: str) -> None:
    """
    在 skills/ 根目录下创建符号链接指向收藏的 skill (支持 Windows/无特权环境自动复制降级)
    平铺在 skills/ 根层级，以便 Antigravity 插件自动发现机制 (第 1 层级) 识别
    """
    # 清理旧版 skills/my 目录（如果存在）
    legacy_my_dir = os.path.join(skills_dir, "my")
    if os.path.exists(legacy_my_dir):
        if os.path.islink(legacy_my_dir):
            os.remove(legacy_my_dir)
        else:
            shutil.rmtree(legacy_my_dir)
        logger.info("Favorites: 已清理旧版 skills/my 目录")

    wanted_links: dict[str, str] = {}
    for fav in favorites:
        source_name = fav["source"]
        for skill_name in fav.get("skills", []):
            source_skill_path = os.path.join(skills_dir, source_name, skill_name)
            if not os.path.isdir(source_skill_path):
                logger.warning(
                    "Favorites: %s/%s 不存在，跳过",
                    source_name,
                    skill_name,
                )
                continue
            relative_target = os.path.join(source_name, skill_name)
            if skill_name in wanted_links:
                logger.warning(
                    "Favorites: skill 名称冲突 '%s'，已有来源将被覆盖",
                    skill_name,
                )
            wanted_links[skill_name] = relative_target

    if not wanted_links:
        logger.info("Favorites: 无配置常用 skill")
        return

    # 清理 skills_dir 下不再在 wanted_links 中且属于旧 favorite 链接/目录的项
    # 注意避免误删 source 来源目录
    source_dirs = {
        d for d in os.listdir(skills_dir)
        if os.path.isdir(os.path.join(skills_dir, d))
        and not os.path.islink(os.path.join(skills_dir, d))
        and any(
            os.path.exists(os.path.join(skills_dir, d, s, "SKILL.md"))
            for s in os.listdir(os.path.join(skills_dir, d))
            if os.path.isdir(os.path.join(skills_dir, d, s))
        )
    }

    for existing in os.listdir(skills_dir):
        if existing in source_dirs:
            continue
        existing_path = os.path.join(skills_dir, existing)
        if existing not in wanted_links:
            if os.path.islink(existing_path):
                os.remove(existing_path)
                logger.info("Favorites: 移除旧链接 %s", existing)
            elif os.path.isdir(existing_path):
                # 仅清理包含 SKILL.md 的平铺副本
                if os.path.exists(os.path.join(existing_path, "SKILL.md")):
                    shutil.rmtree(existing_path)
                    logger.info("Favorites: 移除旧目录 %s", existing)

    for skill_name, relative_target in wanted_links.items():
        link_path = os.path.join(skills_dir, skill_name)
        if os.path.islink(link_path):
            current_target = os.readlink(link_path)
            if current_target == relative_target:
                continue
            os.remove(link_path)
        elif os.path.exists(link_path):
            shutil.rmtree(link_path)

        source_name = relative_target.split(os.sep)[0]
        target_abs_path = os.path.join(skills_dir, source_name, skill_name)

        try:
            os.symlink(relative_target, link_path)
            logger.info("Favorites: %s -> %s", skill_name, relative_target)
        except (OSError, NotImplementedError, PermissionError) as e:
            shutil.copytree(target_abs_path, link_path)
            logger.warning(
                "Favorites: 无法创建符号链接 (%s)，降级为复制目录 %s -> %s",
                e,
                skill_name,
                link_path,
            )

    logger.info("Favorites: 共 %d 个常用 skill ✓", len(wanted_links))


