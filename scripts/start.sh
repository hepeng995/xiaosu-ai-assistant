#!/usr/bin/env bash
# 一键启动全部服务（PostgreSQL + pgvector + Redis + API + Web）
set -euo pipefail

# 切到仓库根目录（脚本位于 scripts/ 下）
cd "$(dirname "$0")/.."

# 确保 .env 存在（首次启动自动从模板复制，提示用户修改占位值）
if [ ! -f .env ]; then
  echo "ℹ️  未找到 .env，已从 .env.example 复制。"
  echo "   请编辑 .env，将 LLM_API_KEY / DINGTALK_* 等 replace_me 占位值改为真实值后重新启动。"
  cp .env.example .env
fi

echo "🚀 启动全部服务（docker compose up --build）..."
docker compose up --build
