#!/bin/bash
# deploy.sh — 部署 Skill Sync 到 Cloud Run Job
#
# 前置条件:
#   1. 已安装 gcloud CLI 并已登录
#   2. 已创建 GitHub PAT 并存入 Secret Manager
#   3. 已启用 Artifact Registry、Cloud Run、Cloud Scheduler API
#
# 使用:
#   chmod +x deploy.sh
#   ./deploy.sh

set -euo pipefail

# ============================================================
# 配置 — 根据实际情况修改
# ============================================================
PROJECT_ID=$(gcloud config get-value project)
REGION="us-west1"
JOB_NAME="skill-sync-job"
IMAGE_NAME="skill-sync"
AR_REPO="cloud-run-source"          # Artifact Registry 仓库名
SECRET_NAME="github-pat"            # Secret Manager 中的 secret 名
GIT_REPO_URL="https://github.com/realmarigold/MySkills.git"
SCHEDULE="0 2 * * *"                # UTC 2:00 = 北京时间 10:00
TIMEZONE="Etc/UTC"

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${IMAGE_NAME}:latest"

# ============================================================
# Step 1: 确保 Artifact Registry 仓库存在
# ============================================================
echo ">>> 检查/创建 Artifact Registry 仓库..."
gcloud artifacts repositories describe "${AR_REPO}" \
    --location="${REGION}" 2>/dev/null || \
gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Docker images for Cloud Run"

# ============================================================
# Step 2: 构建并推送 Docker 镜像
# ============================================================
echo ">>> 构建 Docker 镜像..."
gcloud builds submit --tag "${IMAGE_URI}" .

# ============================================================
# Step 3: 创建/更新 Cloud Run Job
# ============================================================
echo ">>> 部署 Cloud Run Job..."
gcloud run jobs deploy "${JOB_NAME}" \
    --image="${IMAGE_URI}" \
    --region="${REGION}" \
    --task-timeout=600 \
    --max-retries=1 \
    --set-env-vars="GIT_REPO_URL=${GIT_REPO_URL}" \
    --set-secrets="GITHUB_TOKEN=${SECRET_NAME}:latest" \
    --memory=512Mi \
    --cpu=1

# ============================================================
# Step 4: 创建 Cloud Scheduler 定时任务
# ============================================================
echo ">>> 配置 Cloud Scheduler..."

# 获取 Cloud Run Job 的 URI
JOB_URI=$(gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" --format="value(metadata.annotations.'run.googleapis.com/urls')" 2>/dev/null || echo "")

# 使用 gcloud scheduler 创建/更新
gcloud scheduler jobs describe "${JOB_NAME}-scheduler" \
    --location="${REGION}" 2>/dev/null && \
gcloud scheduler jobs update http "${JOB_NAME}-scheduler" \
    --location="${REGION}" \
    --schedule="${SCHEDULE}" \
    --time-zone="${TIMEZONE}" \
    --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
    --http-method=POST \
    --oauth-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com" || \
gcloud scheduler jobs create http "${JOB_NAME}-scheduler" \
    --location="${REGION}" \
    --schedule="${SCHEDULE}" \
    --time-zone="${TIMEZONE}" \
    --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
    --http-method=POST \
    --oauth-service-account-email="${PROJECT_ID}@appspot.gserviceaccount.com"

echo ""
echo "============================================================"
echo "部署完成！"
echo "============================================================"
echo ""
echo "手动执行一次:"
echo "  gcloud run jobs execute ${JOB_NAME} --region ${REGION}"
echo ""
echo "查看日志:"
echo "  gcloud run jobs executions list --job=${JOB_NAME} --region=${REGION}"
echo ""
