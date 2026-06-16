#!/usr/bin/env bash
# 运行自动化测试
#   后端：apps/api （uv run pytest）
#   前端：apps/web （pnpm test，第 9 阶段补齐）
set -euo pipefail
cd "$(dirname "$0")/.."

echo "===== 后端测试 (apps/api: uv run pytest) ====="
cd apps/api
uv run pytest "$@"
# 注：前端测试（apps/web pnpm test）将在第 9 阶段补充
