# Skill Auto-Update Service — 规格说明

## 概述

自动从多个 GitHub 仓库同步 Agent Skill 到 `realmarigold/MySkills`，部署为 Google Cloud Run Job。

## 架构

- **运行方式**: Cloud Run Job（一次性执行，非常驻服务）
- **触发方式**: Cloud Scheduler 每天 UTC 2:00
- **语言**: Python 3.12
- **容器**: python:3.12-slim + git

## 配置格式 (sources.yaml)

```yaml
sources:
  - name: string          # 来源标识，对应 skills/<name>/
    repo: string          # GitHub 仓库 (owner/repo)
    branch: string        # 分支名，默认 main
    path: string          # skill 所在子目录
    mode: exclude|include # 过滤模式
    exclude: [string]     # mode=exclude 时，排除的 skill 名
    include: [string]     # mode=include 时，包含的 skill 名
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `GITHUB_TOKEN` | 是 | GitHub PAT，用于 API 访问和 git push |
| `GIT_REPO_URL` | 否 | 目标仓库 URL，默认 `https://github.com/realmarigold/MySkills.git` |
| `DRY_RUN` | 否 | 设为 `true` 时不执行 push，默认 `false` |

## 同步逻辑

1. Clone 目标仓库到临时目录（空仓库则自动 init + remote add）
2. 读取 `sources.yaml`（仓库中无此文件时使用容器内置默认配置）
3. 对每个 source:
   - 通过 GitHub API 列出 `repo/path` 下所有 skill 目录
   - 根据 mode + include/exclude 过滤
   - 清理本地不再需要的 skill
   - 递归下载每个 skill 的完整目录内容
4. 检测变更，有变化则 commit & push

## 部署

- **Docker 镜像**: 存储在 Artifact Registry (`us-west1-docker.pkg.dev/`)
- **Cloud Run Job**: `skill-sync-job`，区域 `us-west1`
- **Secret**: `github-pat` via Secret Manager
- **Scheduler**: `skill-sync-job-scheduler`，每天 UTC 2:00

## 输出目录结构

```
skills/
└── <source-name>/
    └── <skill-name>/
        ├── SKILL.md
        └── [其他资源文件]
```
