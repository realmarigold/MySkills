"""
main.py - Skill Sync 入口
从多个 GitHub 来源同步 Agent Skill 到目标 Git 仓库

环境变量:
    GITHUB_TOKEN    - GitHub PAT (用于 API 访问和 git push)
    GIT_REPO_URL    - 目标仓库 URL (默认: https://github.com/realmarigold/MySkills.git)
    DRY_RUN         - 设为 "true" 时不执行 git push
"""

import os
import sys
import shutil
import tempfile
import logging
from datetime import datetime, timezone, timedelta

import yaml

from syncer import sync_source
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
            import shutil as _shutil
            _shutil.copy2(fallback, config_path)
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


def main():
    # 读取环境变量
    token = os.environ.get("GITHUB_TOKEN")
    repo_url = os.environ.get(
        "GIT_REPO_URL", "https://github.com/realmarigold/MySkills.git"
    )
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"

    if not token:
        logger.warning("未设置 GITHUB_TOKEN，API 请求可能受限，且无法 push。")

    logger.info("=" * 60)
    logger.info("Skill Sync 开始运行")
    logger.info("目标仓库: %s", repo_url)
    logger.info("Dry Run: %s", dry_run)
    logger.info("=" * 60)

    # 创建临时工作目录
    work_dir = tempfile.mkdtemp(prefix="skill-sync-")
    logger.info("工作目录: %s", work_dir)

    try:
        # 1. Clone 目标仓库
        clone_repo(repo_url, work_dir, token)

        # 2. 加载配置
        config = load_config(work_dir)
        sources = config["sources"]

        # 3. skills 目录
        skills_dir = os.path.join(work_dir, "skills")
        os.makedirs(skills_dir, exist_ok=True)

        # 4. 逐个来源同步
        for source in sources:
            try:
                sync_source(source, skills_dir, token)
            except Exception:
                logger.exception(
                    "同步来源 [%s] 失败，跳过继续", source.get("name", "unknown")
                )

        # 5. 检查变更并推送
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
    logger.info("Skill Sync 运行结束")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
