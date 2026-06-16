# xiaosu-api · 小苏 AI 助手后端

FastAPI 后端，承载 RAG 问答、自研 Tool Calling Agent、IM 适配与 Mock 内部 API。

## 本地开发

```bash
cd apps/api
uv sync                 # 创建 .venv 并安装依赖（含 dev）
uv run pytest           # 运行测试
uv run ruff check .     # lint
uv run uvicorn app.main:app --reload --port 8000   # 本地热重载
```

## 目录结构（第 1 阶段）

```
app/
├── main.py              # FastAPI 入口 + CORS + trace_id 中间件 + lifespan
├── core/                # config / logging / errors
└── api/                 # 路由（health）
tests/                   # pytest
```

后续阶段将逐步加入：`db/` `models/` `schemas/` `services/` `llm/` `agents/` `tools/` `im/` `parsers/`。
