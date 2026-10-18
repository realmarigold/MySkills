"""
main.py - Skill Sync 入口
从多个 GitHub 来源同步 Agent Skill 到目标 Git 仓库（或本地工作区）

环境变量:
    GITHUB_TOKEN    - GitHub PAT (用于 API 访问和 git push)
    GIT_REPO_URL    - 目标仓库 URL (默认: https://github.com/realmarigold/MySkills.git)
    DRY_RUN         - 设为 "true" 时不执行 git push
    LOCAL_SYNC      - 设为 "true" (或传入 --local) 时直接同步当前本地仓库目录
"""

import argparse
import os
import sys
import shutil
import tempfile
import logging
from datetime import datetime, timezone, timedelta

import yaml

from syncer import sync_source, cleanup_skills_dir
from git_ops import clone_repo, has_changes, commit_and_push

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("skill-sync")


def load_config(repo_dir: str) -> dict:
    """
    从仓库根目录加载 sources.yaml
    如果仓库中没有（空仓库首次运行），尝试从容器内的备份加载
    """
    config_path = os.path.join(repo_dir, "sources.yaml")

    if not os.path.exists(config_path):
        # 尝试从容器内的备份加载（Dockerfile COPY 进来的）
        fallback = os.path.join(os.path.dirname(__file__), "sources.default.yaml")
        if os.path.exists(fallback):
            logger.info("仓库中无 sources.yaml，使用内置默认配置")
            shutil.copy2(fallback, config_path)
        else:
            logger.error("配置文件不存在: %s", config_path)
            sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    sources = config.get("sources", [])
    if not sources:
        logger.warning("sources.yaml 中没有定义任何来源，退出。")
        sys.exit(0)

    logger.info("已加载 %d 个来源配置", len(sources))
    return config


def run_sync_in_dir(repo_dir: str, token: str | None = None) -> tuple[set[str], bool]:
    """
    在指定仓库目录内执行全量同步与清理
    返回 (本次激活的全部 skill 名称集合, 是否全部来源同步成功)
    """
    config = load_config(repo_dir)
    sources = config["sources"]

    skills_dir = os.path.join(repo_dir, "skills")
    os.makedirs(skills_dir, exist_ok=True)

    active_skills: set[str] = set()
    all_succeeded = True

    for source in sources:
        try:
            synced = sync_source(source, skills_dir, token)
            for s in synced:
                if s in active_skills:
                    logger.warning("检测到跨来源同名 skill '%s'，后同步的来源将覆盖前者", s)
                active_skills.add(s)
        except Exception:
            all_succeeded = False
            logger.exception(
                "同步来源 [%s] 失败", source.get("name", "unknown")
            )

    if all_succeeded:
        cleanup_skills_dir(skills_dir, active_skills)
    else:
        logger.error("存在同步失败的来源，跳过全量过期清理以避免误删现有 skill")

    # 清理旧版遗留的根目录 skills.json（如果存在）
    legacy_skills_json = os.path.join(repo_dir, "skills.json")
    if os.path.isfile(legacy_skills_json):
        os.remove(legacy_skills_json)
        logger.info("已清理废弃的根目录 skills.json")

    logger.info("当前生效 skill 总数: %d", len(active_skills))
    return active_skills, all_succeeded


def main():
    parser = argparse.ArgumentParser(description="MySkills Sync Runner")
    parser.add_argument(
        "--local",
        action="store_true",
        help="直接在当前本地仓库目录执行同步，不进行临时目录 clone 或远端 push",
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip() or None
    repo_url = os.environ.get(
        "GIT_REPO_URL", "https://github.com/realmarigold/MySkills.git"
    ).strip()
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
    local_mode = args.local or os.environ.get("LOCAL_SYNC", "false").lower() == "true"

    if not token and not local_mode:
        logger.warning("未设置 GITHUB_TOKEN，API 请求可能受限，且无法 push。")

    logger.info("=" * 60)
    logger.info("Skill Sync 开始运行")
    if local_mode:
        local_repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        logger.info("运行模式: 本地仓库直连 (%s)", local_repo_dir)
        logger.info("=" * 60)
        _, all_ok = run_sync_in_dir(local_repo_dir, token)
        logger.info("=" * 60)
        if not all_ok:
            logger.error("本地 Skill Sync 存在失败项 ✗")
            sys.exit(1)
        logger.info("本地 Skill Sync 运行结束 ✓")
        logger.info("=" * 60)
        return

    logger.info("目标仓库: %s", repo_url)
    logger.info("Dry Run: %s", dry_run)
    logger.info("=" * 60)

    # 创建临时工作目录
    work_dir = tempfile.mkdtemp(prefix="skill-sync-")
    logger.info("工作目录: %s", work_dir)
    all_ok = True

    try:
        # 1. Clone 目标仓库
        clone_repo(repo_url, work_dir, token)

        # 2. 执行同步与清理
        _, all_ok = run_sync_in_dir(work_dir, token)

        # 3. 检查变更并推送
        if has_changes(work_dir):
            tz_cn = timezone(timedelta(hours=8))
            now = datetime.now(tz_cn).strftime("%Y-%m-%d %H:%M:%S CST")
            commit_msg = f"chore: sync skills ({now})"

            if dry_run:
                logger.info("[DRY RUN] 检测到变更，但不执行 push。")
                logger.info("[DRY RUN] Commit message: %s", commit_msg)
            else:
                commit_and_push(work_dir, commit_msg)
                logger.info("同步完成，已推送到远端 ✓")
        else:
            logger.info("没有变更，无需推送。")

    finally:
        # 清理临时目录
        shutil.rmtree(work_dir, ignore_errors=True)
        logger.info("清理完成，工作目录已删除。")

    logger.info("=" * 60)
    if not all_ok:
        logger.error("Skill Sync 存在失败来源，以非零状态码退出 ✗")
        sys.exit(1)
    logger.info("Skill Sync 运行结束")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
