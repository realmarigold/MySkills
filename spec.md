# Skill Auto-Update Service — 规格说明

## 概述

自动从多个 GitHub 仓库同步 Agent Skill 到 `realmarigold/MySkills`，严格遵循 **Antigravity 2.0 Plugin 规范**，并支持部署为 Google Cloud Run Job。

## 架构

- **运行方式**: Cloud Run Job（一次性执行，非常驻服务）或本地 `--local` 直连同步
- **触发方式**: Cloud Scheduler 每天 UTC 2:00
- **语言**: Python 3.12
- **容器**: python:3.12-slim + git
- **插件标准**: Antigravity 2.0 Plugin 规范
  - 插件清单: `plugin.json`（含 `name`、`displayName`、`version`、`description`、`logo`、`suggestedPrompts`）
  - 插件图标: `assets/logo.svg`（128x128 透明边距高对比矢量图标）
  - 安装目标: `~/.gemini/config/plugins/myskills`（通过 `install.ps1` / `install.sh` 同步纯净真实目录副本，满足 Antigravity Go Language Server `entry.IsDir()` 扫描要求并即时生效）
  - 技能结构: 纯净一级平铺真实目录 `skills/<skill-name>/SKILL.md`（零符号链接依赖，100% 跨平台兼容）

## 配置格式 (sources.yaml)

```yaml
sources:
  - name: string          # 来源标识
    repo: string          # GitHub 仓库 (owner/repo)
    branch: string        # 分支名，默认 main
    path: string          # 远端仓库中 skill 所在子目录
    mode: exclude|include # 过滤模式
    exclude: [string]     # mode=exclude 时，排除的 skill 名
    include: [string]     # mode=include 时，包含的 skill 名
```

## 环境变量与命令行参数

| 变量 / 参数 | 必填 | 说明 |
|------|------|------|
| `--local` / `LOCAL_SYNC=true` | 否 | 直接同步当前本地仓库目录，不进行临时 clone 或 git push |
| `GITHUB_TOKEN` | 远端模式必填 | GitHub PAT，用于 API 访问和 git push |
| `GIT_REPO_URL` | 否 | 目标仓库 URL，默认 `https://github.com/realmarigold/MySkills.git` |
| `DRY_RUN` | 否 | 设为 `true` 时不执行 push，默认 `false` |

## 同步逻辑

1. 远端模式下 Clone 目标仓库到临时目录（`--local` 模式下直接使用当前工作区根目录）。
2. 读取 `sources.yaml`（仓库中无此文件时使用容器内置默认配置 `sync/sources.default.yaml`）。
3. 对每个 `source`:
   - 通过 GitHub API 列出 `repo/path` 下所有 skill 目录
   - 根据 `mode` + `include`/`exclude` 过滤保留目标 skill
   - 一次性下载仓库 Tarball 归档，将过滤后的 skill 直接解压平铺到 `skills/<skill-name>/`
4. 清理阶段 (`cleanup_skills_dir`):
   - 当所有来源同步成功时，自动移除 `skills/` 下不在本次激活集合中的旧目录、历史二级分类目录（如 `anthropics/`、`mattpocock-*/`、`my/`）及残留符号链接/伪链接文件。
5. 远端模式下检测 Git 变更，有变化则自动 commit & push。

## 部署

- **Docker 镜像**: 存储在 Artifact Registry (`us-west1-docker.pkg.dev/`)
- **Cloud Run Job**: `skill-sync-job`，区域 `us-west1`
- **Secret**: `github-pat` via Secret Manager
- **Scheduler**: `skill-sync-job-scheduler`，每天 UTC 2:00

## 输出目录结构

```text
skills/
└── <skill-name>/
    ├── SKILL.md
    └── [其他资源文件]
```
