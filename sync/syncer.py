"""
syncer.py - 核心同步逻辑
从 GitHub 仓库下载 skill 文件并直接平铺同步到本地 skills/<skill-name>/ 目录，
支持多技能集合仓库 (include/exclude) 与单技能独立仓库 (single)，
确保 100% 符合 Antigravity 2.0 插件一级目录自动发现规范且跨平台零符号链接依赖。
"""

import io
import os
import logging
import shutil
import subprocess
import tarfile
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

IGNORED_ROOT_ENTRIES = {".git", ".github", ".gitignore", ".dockerignore"}


def resolve_github_token(token: str | None = None) -> str | None:
    """
    优先使用传入的 token；若为空（如本地运行未导出 GITHUB_TOKEN），
    尝试通过 git credential fill 获取本地 Git 凭据以支持私有仓库访问。
    """
    if token:
        return token
    try:
        res = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        if res.returncode == 0 and res.stdout:
            for line in res.stdout.splitlines():
                if line.startswith("password="):
                    cred_token = line.split("=", 1)[1].strip()
                    if cred_token:
                        return cred_token
    except Exception:
        pass
    return None


def get_http_session(token: str | None = None) -> requests.Session:
    """创建配置了 Retry 策略和 Auth Header 的 requests.Session"""
    resolved_token = resolve_github_token(token)
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
    if resolved_token:
        session.headers["Authorization"] = f"token {resolved_token}"
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

    url = f"{GITHUB_API}/repos/{repo}/contents/{path}".rstrip("/")
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


def _remove_path(target_path: str) -> None:
    """安全移除文件、符号链接或目录（兼容 Windows 伪符号链接普通文件与真实目录）"""
    if os.path.islink(target_path) or os.path.isfile(target_path):
        os.remove(target_path)
    elif os.path.isdir(target_path):
        shutil.rmtree(target_path)


def extract_single_skill_from_tarball(
    tarball_bytes: bytes,
    remote_path: str,
    skill_name: str,
    skills_dir: str,
) -> None:
    """
    从单技能仓库（SKILL.md 位于仓库根目录或指定子目录）的 Tarball 字节流中提取整个 skill 到 skills_dir/<skill_name>/
    """
    os.makedirs(skills_dir, exist_ok=True)

    with tarfile.open(fileobj=io.BytesIO(tarball_bytes), mode="r:gz") as tar:
        members = tar.getmembers()
        if not members:
            return

        first_member = members[0].name
        top_prefix = first_member.split("/")[0] + "/"

        skill_prefix = top_prefix
        clean_path = remote_path.strip("/")
        if clean_path:
            skill_prefix += clean_path + "/"

        local_skill_path = os.path.join(skills_dir, skill_name)
        if os.path.exists(local_skill_path) or os.path.islink(local_skill_path):
            _remove_path(local_skill_path)
        os.makedirs(local_skill_path, exist_ok=True)

        extracted_count = 0
        for member in members:
            if member.name.startswith(skill_prefix) and member.isfile():
                rel_path = member.name[len(skill_prefix) :]
                if not rel_path:
                    continue
                first_seg = rel_path.split("/")[0]
                if first_seg in IGNORED_ROOT_ENTRIES:
                    continue
                norm_rel = os.path.normpath(rel_path)
                if norm_rel.startswith("..") or os.path.isabs(norm_rel):
                    continue
                target_file = os.path.join(local_skill_path, norm_rel)
                os.makedirs(os.path.dirname(target_file), exist_ok=True)

                extracted_file = tar.extractfile(member)
                if extracted_file:
                    with open(target_file, "wb") as f:
                        shutil.copyfileobj(extracted_file, f)
                    extracted_count += 1

        logger.info("  解压单仓库 skill: %s (%d 个文件)", skill_name, extracted_count)


def extract_skills_from_tarball(
    tarball_bytes: bytes,
    remote_path: str,
    wanted_skills: list[str],
    skills_dir: str,
) -> None:
    """
    从 Tarball 字节流中高效提取需要的 skill 目录，直接平铺到 skills_dir/<skill_name>/
    """
    os.makedirs(skills_dir, exist_ok=True)

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
            local_skill_path = os.path.join(skills_dir, skill_name)

            if os.path.exists(local_skill_path) or os.path.islink(local_skill_path):
                _remove_path(local_skill_path)
            os.makedirs(local_skill_path, exist_ok=True)

            extracted_count = 0
            for member in members:
                if member.name.startswith(skill_prefix) and member.isfile():
                    rel_path = member.name[len(skill_prefix) :]
                    # 防御路径穿越
                    norm_rel = os.path.normpath(rel_path)
                    if norm_rel.startswith("..") or os.path.isabs(norm_rel):
                        continue
                    target_file = os.path.join(local_skill_path, norm_rel)
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
) -> list[str]:
    """
    同步一个来源的 skill 直接平铺到本地 skills/<skill-name>/ 目录
    返回本次成功同步的 skill 名称列表
    """
    if session is None:
        session = get_http_session(token)

    name = source["name"]
    repo = source["repo"]
    branch = source.get("branch", "main")
    path = source.get("path", "")
    mode = source.get("mode", "exclude")

    logger.info("同步来源 [%s] 从 %s ...", name, repo)

    tarball_url = f"{GITHUB_API}/repos/{repo}/tarball/{branch}"

    # 单技能仓库模式：仓库根目录（或指定 path）直接就是单个 Skill
    if mode == "single":
        skill_name = source.get("skill", name)
        logger.info("  单技能仓库模式 -> %s", skill_name)
        logger.info("  正在下载仓库归档文件 (%s)...", tarball_url)
        resp = session.get(tarball_url, timeout=60, allow_redirects=True)
        resp.raise_for_status()
        extract_single_skill_from_tarball(resp.content, path, skill_name, skills_dir)
        logger.info("来源 [%s] 同步完成 ✓", name)
        return [skill_name]

    # 多技能集合仓库模式
    # 1. 获取远端 skill 列表
    all_skills = list_skills(source, token, session=session)
    logger.info("  远端共 %d 个 skill", len(all_skills))

    # 2. 过滤
    wanted_skills = filter_skills(all_skills, source)
    logger.info("  过滤后保留 %d 个: %s", len(wanted_skills), wanted_skills)

    if not wanted_skills:
        logger.info("  没有需要同步的 skill")
        return []

    os.makedirs(skills_dir, exist_ok=True)

    # 3. 一次性下载 Tarball 并解压提取 wanted_skills 到 skills_dir/<skill_name>/
    logger.info("  正在下载仓库归档文件 (%s)...", tarball_url)
    resp = session.get(tarball_url, timeout=60, allow_redirects=True)
    resp.raise_for_status()

    extract_skills_from_tarball(resp.content, path, wanted_skills, skills_dir)
    logger.info("来源 [%s] 同步完成 ✓", name)
    return wanted_skills


def cleanup_skills_dir(skills_dir: str, active_skills: set[str]) -> None:
    """
    清理 skills/ 根目录下不属于 active_skills 的残留项：
    - 移除被淘汰的旧 skill 目录
    - 移除旧版按来源分类的二级容器目录 (如 anthropics/, mattpocock-*/, my/)
    - 移除旧版遗留的符号链接或 Windows 文本伪链接
    """
    if not os.path.isdir(skills_dir):
        return

    for existing in os.listdir(skills_dir):
        existing_path = os.path.join(skills_dir, existing)
        if existing not in active_skills:
            _remove_path(existing_path)
            logger.info("Cleanup: 已移除冗余/过期项 %s", existing)
        elif os.path.islink(existing_path) or os.path.isfile(existing_path):
            _remove_path(existing_path)
            logger.info("Cleanup: 已移除异常非目录项 %s", existing)
