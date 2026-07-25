# MySkills

自动同步 Agent Skill 到本仓库，部署为 Cloud Run Job，由 Cloud Scheduler 每天触发。

## 工作原理

1. Cloud Scheduler 每天 UTC 2:00（北京时间 10:00）触发 Cloud Run Job。
2. Job 克隆本仓库，读取 `sources.yaml` 配置。
3. 通过 GitHub API 结合仓库归档 (Tarball) 一次性高效下载 skill 目录文件，防范 API 请求限流 (429)，并具备指数退避重试机制。
4. 在 `skills/my/` 中自动维护常用 Skill 的快捷方式（在 Windows/非特权模式下支持软链接失败自动回退为目录复制）。
5. 如果有变更则自动 commit & push。

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

## 本地测试与单元测试

```bash
# 1. 安装依赖
pip install -r sync/requirements.txt pytest

# 2. 运行单元测试
python3 -m unittest discover -s tests -v

# 3. 运行本地同步测试 (Dry Run 模式)
export GITHUB_TOKEN=ghp_your_token
export DRY_RUN=true
python sync/main.py
```

## 作为 Antigravity 插件安装使用

本仓库符合 Antigravity 插件规范（包含了 `plugin.json`）。你可以将其安装为 Antigravity 的本地插件，使 Antigravity 能自动识别并加载 `skills/` 目录下的所有 Agent Skill：

### 安装插件

**macOS / Linux (Bash):**
```bash
chmod +x install.sh
./install.sh
```

**Windows (PowerShell):**
```powershell
.\install.ps1
```

### 卸载插件

**macOS / Linux (Bash):**
```bash
./install.sh --uninstall
```

**Windows (PowerShell):**
```powershell
.\install.ps1 -Uninstall
```

## 目录结构

```
├── .github/workflows/ # GitHub Actions CI 配置
│   └── ci.yml
├── plugin.json        # Antigravity 插件配置文件
├── install.sh         # Antigravity 插件安装/卸载脚本 (macOS/Linux)
├── install.ps1        # Antigravity 插件安装/卸载脚本 (Windows PowerShell)
├── sources.yaml       # skill 来源配置
├── skills/            # 同步下来的 skill（自动维护）
│   ├── anthropics/    # 完整同步
│   │   ├── claude-api/
│   │   ├── frontend-design/
│   │   └── ...
│   └── my/            # 常用 skill 符号链接/快捷副本
│       └── claude-api -> ../anthropics/claude-api
├── sync/              # 同步服务代码
│   ├── main.py
│   ├── syncer.py
│   ├── git_ops.py
│   └── requirements.txt
├── tests/             # 自动化单元测试套件
│   └── test_syncer.py
├── Dockerfile
├── deploy.sh
└── spec.md
```


