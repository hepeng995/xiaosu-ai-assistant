#!/usr/bin/env bash
# 代码静态检查
#   后端：ruff + mypy
#   前端：eslint
set -euo pipefail
cd "$(dirname "$0")/.."

echo "===== 后端 lint (apps/api: ruff + mypy) ====="
cd apps/api
uv run ruff check .
uv run mypy app
cd ../..

echo ""
echo "===== 前端 lint (apps/web: eslint) ====="
cd apps/web
pnpm lint
