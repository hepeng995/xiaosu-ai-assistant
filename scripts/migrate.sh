#!/usr/bin/env bash
# 执行数据库迁移：cd apps/api && uv run alembic upgrade head
set -euo pipefail
cd "$(dirname "$0")/.."
cd apps/api

echo "===== 数据库迁移 (alembic upgrade head) ====="
# 本地宿主迁移：连 postgres 容器的宿主映射端口 localhost:5433。
# （容器间通信走 postgres:5432，由容器内 .env 提供；此处覆盖为宿主可达地址）
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://postgres:postgres@localhost:5433/xiaosu}"

uv run alembic upgrade head
