# 小苏 AI 助手

公司内部 AI 助手「小苏」是一套面向企业知识问答与内部系统查询的完整 Demo：员工在钉钉或飞书里 @ 机器人提问，小苏基于 RAG 知识库生成带引用的回答；当问题需要查员工、考勤、订单、当前时间等内部信息时，由自研 Tool Calling Agent 按 Tool Schema 自主选择工具；管理员通过 Web 后台维护知识库、查看对话日志、追踪 Token 与成本。

项目可以在没有真实模型 Key 的情况下跑通端到端流程：`LLM_API_KEY=replace_me` 时自动启用确定性 Mock LLM 与 Mock Embedding，适合本地验收、演示和自动化测试。配置真实 OpenAI-compatible LLM / Embedding、钉钉 / 飞书密钥后，可切换到真实联调。

## 目录

- [项目亮点](#项目亮点)
- [功能截图](#功能截图)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [安装与启动](#安装与启动)
- [环境变量](#环境变量)
- [使用指南](#使用指南)
- [MCP Server](#mcp-server)
- [测试与质量检查](#测试与质量检查)
- [验收问题](#验收问题)
- [Roadmap](#roadmap)
- [常见问题](#常见问题)
- [相关文档](#相关文档)

## 项目亮点

| 能力 | 说明 |
|---|---|
| RAG 知识库问答 | 支持 `md` / `pdf` / `docx` / `txt` 上传，解析、分块、向量化后写入 PostgreSQL + pgvector；回答必须带文件名、章节 / 页码 / 段落、原文 quote 与 score |
| 拒答机制 | 检索无命中、低于阈值、隐私敏感问题、无依据未来问题都会友好拒答，避免编造 |
| 自研 Tool Calling Agent | 工具选择由 LLM 根据 Tool Schema 自主决定，主循环最多 3 轮；内置知识库、员工、考勤、订单、当前时间工具 |
| IM 双平台 | 钉钉与飞书共用 Chat Service 主链路，分别处理验签、消息解析与回复；飞书支持 CardKit 流式卡片、文件上传问答、@ 成员富文本展示并可降级为普通 post |
| Web 管理后台 | 文档管理、分块预览、对话日志、系统设置、调试聊天、Token / 成本概览 |
| MCP Server | 支持 Claude Desktop / Cursor 通过 stdio 或 Streamable HTTP 调用小苏能力 |
| 工程化交付 | Docker Compose 一键启动，uv + pnpm 固定包管理，结构化日志、trace_id、Langfuse noop 降级、自动化测试、Mock 流程全覆盖 |

## 功能截图

| 管理后台概览 | 运营数据面板 |
|---|---|
| ![小苏 AI 后台概览](./admin-overview-light.png) | ![小苏 AI 后台运营数据](./ov-data.png) |

> 截图文件位于仓库根目录。本地启动后访问 `http://localhost:3001/admin` 可查看真实后台界面。

## 系统架构

```mermaid
flowchart LR
    user["员工 / 管理员"] --> dingtalk["钉钉机器人"]
    user --> feishu["飞书机器人"]
    user --> web["Web 后台 / 调试聊天"]
    user --> mcp["Claude Desktop / Cursor"]

    dingtalk --> im["IM Adapter\n验签 / 解密 / 解析"]
    feishu --> im
    web --> chat_api["Chat API / SSE"]
    mcp --> mcp_server["MCP Server\nstdio / Streamable HTTP"]

    im --> chat["Chat Service\n会话隔离 / 敏感词 / 异常兜底"]
    chat_api --> chat
    mcp_server --> chat

    chat --> agent["自研 Agent 主循环\nLLM 按 Tool Schema 选工具\nMAX_TOOL_ROUNDS=3"]
    agent --> llm["OpenAI-compatible LLM\n真实调用或 Mock"]

    agent --> kb_tool["search_knowledge_base"]
    agent --> employee_tool["get_employee"]
    agent --> attendance_tool["get_attendance"]
    agent --> orders_tool["get_orders"]
    agent --> time_tool["get_current_time"]

    kb_tool --> retrieval["Retrieval Service\nRAG_TOP_K / 阈值拒答"]
    retrieval --> vector_db["PostgreSQL 16 + pgvector\n文档分块与向量"]
    employee_tool --> mock_api["Mock API\n/mock-api/*"]
    attendance_tool --> mock_api
    orders_tool --> mock_api

    chat --> db["messages / tool_call_logs\nToken / 成本 / 引用"]
    chat --> reply["Markdown / 飞书 post / SSE 回复\n友好兜底"]
```

核心链路：`IM/Web/MCP → chat_service → Agent → LLM + Tools → RAG/Mock API → 引用与工具结果回填 → 最终回答 → 落库与日志`。`trace_id` 贯穿请求、Agent、工具、LLM、数据库日志，便于排障。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12+、FastAPI、Pydantic v2、SQLAlchemy 2.x Async、Alembic、httpx、loguru、pytest、uv |
| 数据与缓存 | PostgreSQL 16、pgvector、Redis 7 |
| 前端 | Next.js 16、React 19、TypeScript、Tailwind CSS v4、lucide-react、pnpm |
| AI 能力 | OpenAI-compatible LLM、OpenAI-compatible Embedding、RAG、自研 Tool Calling Agent、Mock LLM / Mock Embedding |
| IM 与集成 | 钉钉机器人、飞书机器人、MCP SDK、Streamable HTTP |
| 基建 | Docker Compose、分文件日志、`.env` 外置配置 |

## 目录结构

```text
xiaosu-ai-assistant/
├── apps/
│   ├── api/                  # FastAPI 后端：RAG、Agent、IM、MCP、Mock API、Alembic 迁移
│   └── web/                  # Next.js 管理后台
├── data/
│   ├── mock/                 # 员工、考勤、订单 Mock 数据
│   └── samples/              # 知识库样本文档
├── logs/                     # app/error/llm/im/indexing/tool 日志
├── scripts/                  # start/test/lint/migrate/seed 脚本
├── storage/uploads/          # 上传文件存储
├── docker-compose.yml
├── .env.example
└── README.md
```

## 安装与启动

### 前置依赖

- Docker Desktop / Docker Compose
- Python 3.12+
- uv
- Node.js 20+ 与 pnpm

在 Windows 上建议使用 Git Bash 或 WSL 执行 `scripts/*.sh`；也可以直接执行等价的 Docker / uv / pnpm 命令。

### 方式一：Docker Compose 一键启动

```bash
cp .env.example .env
./scripts/start.sh
./scripts/migrate.sh
./scripts/seed.sh
curl http://localhost:8000/health
```

启动后服务地址：

| 服务 | 地址 |
|---|---|
| API | http://localhost:8000 |
| Web 后台 | http://localhost:3001 |
| PostgreSQL | localhost:5433 |
| Redis | localhost:6380 |

`GET /health` 预期返回：

```json
{"status":"ok","service":"xiaosu-api"}
```

### 方式二：本地开发模式

先启动 PostgreSQL 与 Redis：

```bash
docker compose up -d postgres redis
```

后端：

```bash
cd apps/api
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

本地直连数据库时，把 `.env` 中容器主机名改为宿主端口：

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/xiaosu
REDIS_URL=redis://localhost:6380/0
```

前端：

```bash
cd apps/web
pnpm install
pnpm dev
```

如果本机 3000 被占用，可让 Next.js 自动换端口；Docker Compose 模式固定映射到 `http://localhost:3001`。

## 环境变量

完整配置见 [`.env.example`](./.env.example)。敏感值必须只写入本地 `.env`，不要提交到 Git。

| 分类 | 关键变量 | 说明 |
|---|---|---|
| 应用 | `APP_ENV`、`APP_PORT`、`WEB_BASE_URL`、`CORS_ALLOW_ORIGINS` | 应用环境、API 端口、后台访问地址、CORS 白名单（逗号分隔，生产必配） |
| 数据库 | `DATABASE_URL`、`REDIS_URL` | Docker 模式使用 `postgres` / `redis`，本地直连使用 `localhost:5433` / `6380` |
| LLM | `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_TIMEOUT_SECONDS`、`LLM_MAX_RETRIES` | OpenAI-compatible Chat Completion 配置；`replace_me` 时走 Mock |
| Embedding | `EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSION` | 向量维度默认 1536，必须与 pgvector 字段一致 |
| RAG | `RAG_TOP_K`、`RAG_SCORE_THRESHOLD`、`RAG_CHUNK_SIZE`、`RAG_CHUNK_OVERLAP` | 默认阈值 0.72，分块 800 / overlap 120 |
| Agent | `MAX_TOOL_ROUNDS`、`TOOL_TIMEOUT_SECONDS` | 工具最多 3 轮，工具超时 10 秒 |
| 钉钉 | `DINGTALK_APP_KEY`、`DINGTALK_APP_SECRET`、`DINGTALK_ROBOT_CODE`、`DINGTALK_CALLBACK_TOKEN`、`DINGTALK_AES_KEY` | 机器人与回调验签配置 |
| 飞书 | `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_VERIFICATION_TOKEN`、`FEISHU_ENCRYPT_KEY`、`FEISHU_STREAMING_ENABLED` | 自建应用、事件订阅、CardKit 流式卡片 |
| MCP | `MCP_SERVER_NAME`、`MCP_HTTP_ENABLED`、`MCP_HTTP_PATH`、`MCP_HTTP_AUTH_TOKEN` | stdio 与 Streamable HTTP 配置 |
| 可观测性 | `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_HOST` | 未配置时保持 noop，不影响主链路 |
| 前端 | `NEXT_PUBLIC_API_BASE_URL` | 浏览器端 API 地址 |

安全约定：

- `.env` 不入库，`.env.example` 只放占位值。
- 日志、前端设置页、错误信息都不回显明文 Key / Secret。
- 生产环境 IM 回调必须配置验签密钥；开发环境缺失时会放行并写告警日志。

生产部署安全清单（以下配置未填写时会回退开发默认值并启动告警，上线必须全部配置）：

| 配置项 | 说明 | 未配置后果 |
|---|---|---|
| `ADMIN_PASSWORD_HASH` | 管理员密码哈希，`cd apps/api && uv run python -m app.core.security 你的密码` 生成 | 回退默认密码 `admin123` |
| `JWT_SECRET_KEY` | JWT 签名密钥，建议 `openssl rand -hex 32` | 每次启动随机生成，重启后已登录 token 全失效 |
| `CORS_ALLOW_ORIGINS` | CORS 白名单，如 `https://cafer.top` | 默认 `*` 允许任意来源（不安全） |
| `DINGTALK_*` / `FEISHU_*` | IM 验签密钥与加密 Key | 开发放行并告警，生产可被伪造回调 |

## 使用指南

### Web 后台

访问 `http://localhost:3001/admin`：

| 页面 | 用途 |
|---|---|
| 概览 | 查看文档数、索引数、对话数、回复成功率、Token 与成本 |
| 文档管理 | 上传 `md/pdf/docx/txt`，查看索引状态、分块引用、同名替换版本 |
| 对话日志 | 按平台、用户、成功状态查看消息、工具调用、Token、耗时和错误码 |
| 系统设置 | 查看 LLM、Embedding、IM、Langfuse 等配置是否已生效，不展示明文密钥 |
| 调试聊天 | 在浏览器内直接验证 RAG、工具调用、多轮指代与拒答 |

### 知识库

1. 启动 API、Web、PostgreSQL、Redis。
2. 执行 `./scripts/seed.sh` 生成样本文档，或在后台上传自己的文档。
3. 上传后系统会解析、分块、向量化并写入 `document_chunks`。
4. 问答命中文档时，回答会带引用；无依据时返回拒答文案。

同名文件会触发替换：旧文档与旧 chunk 软删除，新文档 `version+1`，检索只命中新版本。

### API 调试

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"platform\":\"web\",\"conversation_id\":\"demo\",\"user_id\":\"u1\",\"message\":\"员工 001 是哪个部门的？\"}"
```

也可以使用后台「调试聊天」页面验证多轮问题，例如先问「员工 001 是谁？」，再问「他上周来上班几天？」。

### 钉钉机器人

1. 在钉钉开放平台创建企业内部应用 / 机器人，获取 `AppKey`、`AppSecret`、`RobotCode`。
2. 配置消息接收地址：`https://<your-domain>/api/im/dingtalk/callback`。
3. 将 `DINGTALK_*` 写入 `.env`。
4. 在群里 @ 机器人提问，或私聊机器人验证。

钉钉适配层会完成验签、消息解析、`IMMessage` 归一化，并通过 `sessionWebhook` 被动回复 Markdown。

### 飞书机器人

1. 在飞书开放平台创建企业自建应用，获取 `App ID` 与 `App Secret`。
2. 事件订阅 Request URL：`https://<your-domain>/api/im/feishu/callback`。
3. 订阅 `im.message.receive_v1`。
4. 将 `FEISHU_*` 写入 `.env`；如配置 Encrypt Key，系统会进行 AES 解密与 `X-Lark-Signature` 校验。
5. 群聊 @ 或私聊机器人即可复用同一条 Chat / RAG / Agent 主链路。

`FEISHU_STREAMING_ENABLED=true` 时优先使用 CardKit 流式卡片；创建或更新卡片失败会降级为一次性 post，保证 IM 端有兜底回复。

## MCP Server

MCP 能力复用小苏现有主链路：`xiaosu_chat` 走 `chat_service`，RAG 仍带引用且无依据拒答；`xiaosu_get_employee`、`xiaosu_get_attendance`、`xiaosu_get_orders`、`xiaosu_get_current_time` 复用现有工具实现。员工、考勤、订单工具依赖本机 FastAPI 的 `/mock-api/*`，本地联调时建议同时启动 API。

### Claude Desktop stdio

```json
{
  "mcpServers": {
    "xiaosu": {
      "command": "uv",
      "args": [
        "--directory",
        "F:\\program\\xiaosu-ai-assistant\\apps\\api",
        "run",
        "python",
        "-m",
        "app.mcp.server"
      ],
      "env": {
        "DATABASE_URL": "postgresql+psycopg://postgres:postgres@localhost:5433/xiaosu",
        "REDIS_URL": "redis://localhost:6380/0"
      }
    }
  }
}
```

### Streamable HTTP

`.env`：

```env
MCP_HTTP_ENABLED=true
MCP_HTTP_PATH=/mcp
MCP_HTTP_AUTH_TOKEN=replace_me
```

生产环境必须把 `MCP_HTTP_AUTH_TOKEN` 改成真实 Token，并在客户端请求头中带上：

```json
{
  "mcpServers": {
    "xiaosu": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer <your-token>"
      }
    }
  }
}
```

## 测试与质量检查

常用脚本：

```bash
./scripts/test.sh
./scripts/lint.sh
./scripts/migrate.sh
./scripts/seed.sh
```

后端单独运行：

```bash
cd apps/api
uv run pytest
uv run pytest tests/test_agent_tool_call.py
uv run ruff check .
uv run mypy app
```

前端单独运行：

```bash
cd apps/web
pnpm lint
pnpm build
```

当前测试覆盖健康检查、文档解析、Mock LLM 工具调用、MCP 入口、IM Adapter、设置模型切换与若干增强项。测试默认不依赖真实 API Key，未配置时走 Mock LLM / Mock Embedding。

提交前建议执行：

```bash
git status
git log -p | grep -iE "api_key|secret|sk-"
```

## 验收问题

| 类型 | 问题 | 预期 |
|---|---|---|
| 知识库 | 员工每年有几天年假？ | 命中员工制度类文档，回答带引用 |
| 知识库 | 报销发票需要什么材料？ | 命中文档并返回定位信息 |
| 工具调用 | 员工 001 是哪个部门的？ | LLM 选择 `get_employee`，返回研发部等员工信息 |
| 工具调用 | 上周一共多少订单？ | LLM 选择 `get_orders`，返回 Mock 订单统计 |
| 工具调用 | 现在几点？ | LLM 选择 `get_current_time` |
| 多轮指代 | 他上周来上班几天？ | 结合上文指代员工，选择考勤工具 |
| 拒答 | CEO 的家庭住址？ | 隐私拒答 |
| 拒答 | 2030 年销售目标？ | 当前知识库无依据时拒答 |
| 鲁棒性 | 模型 Key 无效或服务超时 | 返回友好兜底，不向 IM 暴露 500 或技术细节 |
| 飞书富消息 | 在群聊中 @ 成员并上传 `md/pdf/docx/txt` 文件 | 文件加入知识库后可继续问答，回复保留 @ 成员富文本 |

`scripts/eval.py --json` 会输出 `summary` 分维度统计（knowledge / tool / multiturn / refuse），便于真实 LLM 联调后快速定位短板。真实钉钉 / 飞书沙箱验收需要配置平台密钥、公网 HTTPS 回调、LLM / Embedding Key；未配置时仍可跑 mock 结构验证。

## Roadmap

| 阶段 | 状态 | 说明 |
|---|---|---|
| 0 项目准备 | 已完成 | 仓库、规范、需求文档、基础脚本 |
| 1 工程骨架 | 已完成 | FastAPI、Next.js、Docker Compose、配置体系 |
| 2 数据模型 | 已完成 | PostgreSQL、pgvector、Alembic、核心表 |
| 3 文档知识库 | 已完成 | 上传、解析、分块、向量化、同名替换 |
| 4 RAG 问答 | 已完成 | 检索、引用、拒答、Mock / 真实双分支 |
| 5 工具调用 | 已完成 | 自研 Agent 主循环、Tool Schema、Mock API |
| 6 IM 集成 | 已完成 | 钉钉、飞书、验签、兜底回复 |
| 7 Web 后台 | 已完成 | 文档、日志、设置、调试聊天 |
| 8 鲁棒性 | 已完成 | 超时、重试、错误码、结构化日志 |
| 9 自动化测试 | 已完成 | pytest 覆盖核心链路与增强项 |
| 10 交付文档 | 已完成 | README、AI_USAGE、自评与开发计划 |
| 11 MCP Server | 已完成 | Claude Desktop / Cursor stdio 与 Streamable HTTP |

后续增强方向：

| 方向 | 优先级 | 说明 |
|---|---|---|
| 真实 LLM / Embedding 联调脚本 | 高 | 已有 eval 脚本；真实结果需填入平台 Key 后执行 |
| 钉钉 / 飞书沙箱验收记录 | 高 | 已固化 IM 回调、验签、群聊 @、文件上传问答路径；截图与真实输出需在沙箱跑完后补充 |
| 集成测试 | 中 | pytest 覆盖上传、IM callback、流式、MCP、成本、观测与富消息关键路径 |
| 前端组件系统 | 已完成 | 已接入 shadcn 风格组件并覆盖后台主要页面 |
| Langfuse + Evals | 已完成 | Langfuse 未配置时 noop，LLM/Embedding/Chat/Retrieval/Tool span 可关联 trace_id；eval 输出分维度 JSON |
| 权限与多租户 | 低 | 后台登录、角色权限、租户隔离、审计导出 |

## 常见问题

### 没有模型 Key 能跑吗？

可以。`.env` 中 `LLM_API_KEY=replace_me`、`EMBEDDING_API_KEY=replace_me` 时自动启用 Mock 分支，适合本地演示、测试与评分验收。配置真实 Key 后会走真实 LLM 与 Embedding。

### Docker 里 API 能启动，本地 uvicorn 连接不上数据库？

Docker Compose 内部使用 `postgres:5432`、`redis:6379`；宿主机本地进程需要使用 `localhost:5433`、`localhost:6380`。把 `.env` 的 `DATABASE_URL` 和 `REDIS_URL` 改成本地端口即可。

### Web 页面提示无法连接后端？

确认 API 已启动并通过 `curl http://localhost:8000/health`。如果前端不是 Docker 模式启动，检查 `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` 是否在构建 / 启动前生效。

### RAG 为什么会拒答？

系统要求回答必须有知识库依据。检索为空、top1 分数低于 `RAG_SCORE_THRESHOLD`，或问题涉及隐私 / 无依据未来信息时，都会拒答而不是编造。

### 飞书流式卡片失败怎么办？

确认应用已开通 `cardkit:card:write` 权限，并检查 `FEISHU_STREAMING_ENABLED`。即使流式卡片失败，系统也会降级为普通 post 回复。

## 相关文档

- [AI_USAGE.md](./AI_USAGE.md)
- [自评.md](./自评.md)

> 其余设计文档（增强计划、审查报告、真实联调记录等）为内部资料，未随仓库公开。
