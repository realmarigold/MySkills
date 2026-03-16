FROM python:3.12-slim

# 安装 git
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY sync/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制同步代码
COPY sync/ ./sync/

# 内置默认 sources.yaml（空仓库首次运行时使用）
COPY sources.yaml ./sync/sources.default.yaml

CMD ["python", "sync/main.py"]
