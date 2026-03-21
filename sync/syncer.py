"""
syncer.py - 核心同步逻辑
从 GitHub 仓库下载 skill 文件到本地目录
"""

import os
import logging
import requests
import shutil

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def get_headers(token: str | None) -> dict:
    """构建 GitHub API 请求头"""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def list_skills(source: dict, token: str | None) -> list[str]:
    """
    列出某个来源下的所有 skill 目录名
    返回: ['claude-api', 'frontend-design', ...]
    """
    repo = source["repo"]
    branch = source.get("branch", "main")
    path = source.get("path", "")

    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    params = {"ref": branch}
    resp = requests.get(url, headers=get_headers(token), params=params, timeout=30)
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


def download_directory(
    repo: str,
    branch: str,
    remote_path: str,
    local_path: str,
    token: str | None,
) -> None:
    """
    递归下载 GitHub 仓库中某个目录的全部内容到本地
    """
    url = f"{GITHUB_API}/repos/{repo}/contents/{remote_path}"
    params = {"ref": branch}
    resp = requests.get(url, headers=get_headers(token), params=params, timeout=30)
    resp.raise_for_status()

    items = resp.json()
    os.makedirs(local_path, exist_ok=True)

    for item in items:
        target = os.path.join(local_path, item["name"])

        if item["type"] == "file":
            logger.debug("  下载: %s", item["path"])
            file_resp = requests.get(
                item["download_url"], headers=get_headers(token), timeout=60
            )
            file_resp.raise_for_status()
            with open(target, "wb") as f:
                f.write(file_resp.content)

        elif item["type"] == "dir":
            download_directory(repo, branch, item["path"], target, token)


def sync_source(source: dict, skills_dir: str, token: str | None) -> None:
    """
    同步一个来源的 skill 到本地 skills/<source-name>/ 目录

    Args:
        source: 来源配置 (name, repo, branch, path, mode, include/exclude)
        skills_dir: 本地 skills/ 根目录
        token: GitHub token
    """
    name = source["name"]
    repo = source["repo"]
    branch = source.get("branch", "main")
    path = source.get("path", "")

    source_dir = os.path.join(skills_dir, name)
    logger.info("同步来源 [%s] 从 %s ...", name, repo)

    # 1. 获取远端 skill 列表
    all_skills = list_skills(source, token)
    logger.info("  远端共 %d 个 skill", len(all_skills))

    # 2. 过滤
    wanted_skills = filter_skills(all_skills, source)
    logger.info("  过滤后保留 %d 个: %s", len(wanted_skills), wanted_skills)

    # 3. 清理：删除本地存在但不再需要的 skill
    if os.path.isdir(source_dir):
        existing = set(os.listdir(source_dir))
        to_remove = existing - set(wanted_skills)
        for skill_name in to_remove:
            remove_path = os.path.join(source_dir, skill_name)
            if os.path.isdir(remove_path):
                logger.info("  删除不再需要的 skill: %s", skill_name)
                shutil.rmtree(remove_path)

    # 4. 下载每个 skill
    os.makedirs(source_dir, exist_ok=True)
    for skill_name in wanted_skills:
        remote_skill_path = f"{path}/{skill_name}" if path else skill_name
        local_skill_path = os.path.join(source_dir, skill_name)

        # 先清空本地目录（确保完全覆盖更新）
        if os.path.isdir(local_skill_path):
            shutil.rmtree(local_skill_path)

        logger.info("  下载 skill: %s", skill_name)
        download_directory(repo, branch, remote_skill_path, local_skill_path, token)

    logger.info("来源 [%s] 同步完成 ✓", name)


def build_favorites(favorites: list[dict], skills_dir: str) -> None:
    """
    在 skills/my/ 下创建符号链接指向收藏的 skill

    Args:
        favorites: [{"source": "anthropics", "skills": ["claude-api", ...]}, ...]
        skills_dir: 本地 skills/ 根目录
    """
    my_dir = os.path.join(skills_dir, "my")

    # 收集所有应该存在的链接
    wanted_links: dict[str, str] = {}  # skill_name -> relative_target
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
            # 相对路径: ../source_name/skill_name
            relative_target = os.path.join("..", source_name, skill_name)
            if skill_name in wanted_links:
                logger.warning(
                    "Favorites: skill 名称冲突 '%s'，已有来源将被覆盖",
                    skill_name,
                )
            wanted_links[skill_name] = relative_target

    if not wanted_links:
        # 没有 favorites，清理整个 my/ 目录（如果存在）
        if os.path.isdir(my_dir):
            shutil.rmtree(my_dir)
            logger.info("Favorites: 无配置，已清理 my/ 目录")
        return

    os.makedirs(my_dir, exist_ok=True)

    # 清理不再需要的链接
    if os.path.isdir(my_dir):
        for existing in os.listdir(my_dir):
            existing_path = os.path.join(my_dir, existing)
            if existing not in wanted_links:
                if os.path.islink(existing_path):
                    os.remove(existing_path)
                    logger.info("Favorites: 移除旧链接 %s", existing)
                elif os.path.isdir(existing_path):
                    shutil.rmtree(existing_path)
                    logger.info("Favorites: 移除旧目录 %s", existing)

    # 创建/更新链接
    for skill_name, relative_target in wanted_links.items():
        link_path = os.path.join(my_dir, skill_name)
        if os.path.islink(link_path):
            current_target = os.readlink(link_path)
            if current_target == relative_target:
                continue  # 链接已正确
            os.remove(link_path)
        elif os.path.exists(link_path):
            shutil.rmtree(link_path)

        os.symlink(relative_target, link_path)
        logger.info("Favorites: %s -> %s", skill_name, relative_target)

    logger.info("Favorites: 共 %d 个常用 skill ✓", len(wanted_links))
