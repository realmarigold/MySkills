"""
git_ops.py - Git 操作封装
处理 clone、检测变更、commit & push
"""

import os
import subprocess
import logging

logger = logging.getLogger(__name__)


def run_git(args: list[str], cwd: str) -> str:
    """执行 git 命令并返回 stdout"""
    cmd = ["git"] + args
    logger.debug("执行: %s (cwd=%s)", " ".join(cmd), cwd)
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return result.stdout.strip()


def clone_repo(repo_url: str, dest: str, token: str | None = None) -> None:
    """
    浅克隆仓库到 dest 目录
    如果提供了 token，将其嵌入 URL 中用于认证
    如果仓库为空（无 commit），则初始化新仓库并添加 remote
    """
    if token:
        # https://github.com/user/repo.git -> https://<token>@github.com/user/repo.git
        auth_url = repo_url.replace("https://", f"https://x-access-token:{token}@")
    else:
        auth_url = repo_url

    logger.info("Cloning %s -> %s", repo_url, dest)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", auth_url, dest],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        # 空仓库 clone 会失败，回退到 init + remote add
        logger.warning("Clone 失败（可能是空仓库），初始化新仓库...")
        os.makedirs(dest, exist_ok=True)
        run_git(["init"], cwd=dest)
        run_git(["remote", "add", "origin", auth_url], cwd=dest)
        run_git(["checkout", "-b", "main"], cwd=dest)

    # 配置 git user（Cloud Run 环境中没有全局配置）
    run_git(["config", "user.email", "skill-sync-bot@noreply.github.com"], cwd=dest)
    run_git(["config", "user.name", "Skill Sync Bot"], cwd=dest)


def has_changes(repo_dir: str) -> bool:
    """检查工作目录是否有变更（包括新文件和修改）"""
    # 先 add 所有变更
    run_git(["add", "-A"], cwd=repo_dir)
    # 检查 staged 变更
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=repo_dir,
        capture_output=True,
        timeout=30,
    )
    # exit code 0 = no changes, 1 = has changes
    return result.returncode != 0


def commit_and_push(repo_dir: str, message: str) -> None:
    """提交并推送变更"""
    run_git(["commit", "-m", message], cwd=repo_dir)
    logger.info("Pushing changes...")
    run_git(["push", "origin", "main"], cwd=repo_dir)
    logger.info("Push 完成 ✓")
