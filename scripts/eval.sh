#!/usr/bin/env bash
# 运行自动化评测（≥20 case，对齐笔试题 7.1–7.5 验收题）
#   用法：./scripts/eval.sh [--json]
#   真实 key：评真实准确率（含 LLM-as-judge 语义评测）
#   未配 key：跑 mock 结构验证（流程 + 工具选择启发式）
# 依赖：需可连通的 PostgreSQL（chat_service 会落库），先 ./scripts/start.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "===== 自动化评测 (scripts/eval.py) ====="
cd apps/api
uv run python ../../scripts/eval.py "$@"
