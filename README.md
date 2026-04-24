# MySkills

自动同步 Agent Skill 到本仓库，部署为 Cloud Run Job，由 Cloud Scheduler 每天触发。

## 工作原理

1. Cloud Scheduler 每天 UTC 2:00（北京时间 10:00）触发 Cloud Run Job
2. Job 克隆本仓库，读取 `sources.yaml` 配置
3. 通过 GitHub API 从各来源下载 skill 文件到 `skills/` 目录
4. 如果有变更则自动 commit & push

## 配置 Skill 来源

编辑 `sources.yaml`：

```yaml
sources:
  # 获取全部，排除指定的
  - name: anthropics
    repo: anthropics/skills
    branch: main
    path: skills
    mode: exclude
    exclude:
      - brand-guidelines

  # 只获取指定的
  - name: another-source
    repo: some-org/some-repo
    branch: main
    path: skills
    mode: include
    include:
      - skill-a
      - skill-b
```

### 配置常用 Skill 精选

在 `sources.yaml` 中添加 `favorites` 段，从已有来源中挑选常用 skill，会在 `skills/my/` 下创建符号链接：

```yaml
favorites:
  - source: anthropics
    skills:
      - frontend-design
      - claude-api
```

这样 `skills/my/` 下会包含扁平化的符号链接，方便直接引用常用 skill，同时不影响完整同步。

## 首次部署

### 1. 创建 GitHub PAT

1. 访问 [GitHub Settings → Fine-grained tokens](https://github.com/settings/tokens?type=beta)
2. 创建 token，选择仅 `realmarigold/MySkills` 仓库
3. 权限: **Contents → Read and write**

### 2. 存入 Secret Manager

```bash
echo -n "ghp_your_token_here" | \
  gcloud secrets create github-pat --data-file=-
```

### 3. 部署

```bash
chmod +x deploy.sh
./deploy.sh
```

### 4. 手动触发测试

```bash
gcloud run jobs execute skill-sync-job --region us-west1
```

## 本地测试

```bash
pip install -r sync/requirements.txt
export GITHUB_TOKEN=ghp_your_token
export DRY_RUN=true
python sync/main.py
```

## 目录结构

```
├── sources.yaml       # skill 来源配置
├── skills/            # 同步下来的 skill（自动维护）
│   ├── anthropics/    # 完整同步
│   │   ├── claude-api/
│   │   ├── frontend-design/
│   │   └── ...
│   └── my/            # 常用 skill 符号链接
│       └── claude-api -> ../anthropics/claude-api
├── sync/              # 同步服务代码
│   ├── main.py
│   ├── syncer.py
│   ├── git_ops.py
│   └── requirements.txt
├── Dockerfile
├── deploy.sh
└── spec.md
```
