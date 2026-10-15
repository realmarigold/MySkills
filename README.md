# MySkills

自动从多个 GitHub 来源同步精选 Agent Skill 到本仓库，完全遵循 **Antigravity 2.0 插件规范**，并支持部署为 Google Cloud Run Job（由 Cloud Scheduler 每天自动触发）。

## 工作原理

1. Cloud Scheduler 每天 UTC 2:00（北京时间 10:00）触发 Cloud Run Job。
2. Job 克隆本仓库，读取 `sources.yaml` 配置。
3. 通过 GitHub API 结合仓库归档 (Tarball) 一次性高效下载所需 skill 文件，防范 API 请求限流 (429) 并具备指数退避重试机制。
4. **纯净平铺结构**：所有过滤后的有效 Skill 直接以真实目录形式解压到 `skills/<skill-name>/`，100% 符合 Antigravity 2.0 插件一级目录自动发现规范（`skills/<skill-name>/SKILL.md`），彻底消除 Git 符号链接在 Windows 下退化为普通文件导致无法加载的问题。

## 配置 Skill 来源

编辑 `sources.yaml`：

```yaml
sources:
  # mode: exclude — 获取该来源下全部 skill，排除指定项
  - name: anthropics
    repo: anthropics/skills
    branch: main
    path: skills
    mode: exclude
    exclude:
      - brand-guidelines
      - internal-comms
      - academy-guide
      - discernment-nudge

  # mode: include — 仅获取 include 列表中指定的 skill
  - name: mattpocock-engineering
    repo: mattpocock/skills
    branch: main
    path: skills/engineering
    mode: include
    include:
      - grill-with-docs
      - tdd
      - diagnosing-bugs
      - to-spec
      - wayfinder
      - improve-codebase-architecture
```

## 作为 Antigravity 2.0 插件安装使用

本仓库严格遵循 Antigravity 2.0 插件规范（包含标准 `plugin.json`、`assets/logo.svg` 以及平铺的 `skills/<skill-name>/SKILL.md`）。

### 安装 / 更新插件

> Antigravity 2.0 底层 Language Server (Go `os.ReadDir`) 扫描 `~/.gemini/config/plugins/` 时要求插件目录必须为**真实文件夹**（会跳过顶层 Symlink / Junction）。安装脚本会将纯净的插件包（`plugin.json`、`assets/`、`skills/`）直接安装至 `~/.gemini/config/plugins/myskills` 并立即生效。

**Windows (PowerShell):**
```powershell
.\install.ps1
```

**macOS / Linux (Bash):**
```bash
chmod +x install.sh
./install.sh
```

> 安装完成后无需重启即可在 Antigravity 中访问 `customization://myskills` 查看与管理插件。

### 卸载插件

**Windows (PowerShell):**
```powershell
.\install.ps1 -Uninstall
```

**macOS / Linux (Bash):**
```bash
./install.sh --uninstall
```

## 本地同步与单元测试

```bash
# 1. 安装依赖
pip install -r sync/requirements.txt pytest

# 2. 运行单元测试
python -m unittest discover -s tests -v

# 3. 直接在本地工作区执行同步更新（无需克隆到临时目录或 push）
python sync/main.py --local

# 4. 模拟 Cloud Run 远端同步测试 (Dry Run 模式)
export GITHUB_TOKEN=ghp_your_token
export DRY_RUN=true
python sync/main.py
```

## Cloud Run 首次部署与更新

### 1. 创建 GitHub PAT

1. 访问 [GitHub Settings → Fine-grained tokens](https://github.com/settings/tokens?type=beta)
2. 创建 token，选择仅 `realmarigold/MySkills` 仓库
3. 权限: **Contents → Read and write**

### 2. 存入 Secret Manager

```bash
echo -n "ghp_your_token_here" | \
  gcloud secrets create github-pat --data-file=-
```

### 3. 部署 / 更新镜像

```bash
chmod +x deploy.sh
./deploy.sh
```

### 4. 手动触发测试

```bash
gcloud run jobs execute skill-sync-job --region us-west1
```

## 目录结构

```text
├── .github/workflows/ # GitHub Actions CI 配置
│   └── ci.yml
├── assets/
│   └── logo.svg       # Antigravity 2.0 插件高清矢量图标
├── plugin.json        # Antigravity 2.0 插件清单 (Manifest)
├── install.sh         # Antigravity 插件安装/卸载脚本 (macOS/Linux)
├── install.ps1        # Antigravity 插件安装/卸载脚本 (Windows PowerShell)
├── sources.yaml       # Skill 来源与过滤配置
├── skills/            # 纯净平铺的真实 Skill 目录（自动维护）
│   ├── claude-api/
│   │   └── SKILL.md
│   ├── frontend-design/
│   │   └── SKILL.md
│   └── ...
├── sync/              # 同步服务核心代码
│   ├── main.py
│   ├── syncer.py
│   ├── git_ops.py
│   ├── sources.default.yaml
│   └── requirements.txt
├── tests/             # 自动化单元测试套件
│   └── test_syncer.py
├── Dockerfile
├── deploy.sh
└── spec.md
```
