# 小苏 AI 助手（Xiaosu AI Assistant）

> 公司内部 AI 助手「小苏」：员工在钉钉里 @ 机器人提问，系统基于 **RAG 知识库**回答（**带引用、可拒答**），并通过**自研 Tool Calling Agent**调用内部 Mock API 工具；管理员通过 **Web 后台**管理文档、查看对话日志与 Token 消耗。

## ✨ 核心功能

| # | 功能 | 说明 |
|---|------|------|
| 1 | 📚 文档知识库 | 上传 md/pdf/docx/txt，解析→分块→向量化→pgvector 入库；列表/删除/同名替换 |
| 2 | 💬 智能问答（RAG） | 基于知识库回答，**带引用**（文件名+章节），无依据**拒答**；多轮 + SSE 流式 |
| 3 | 🔧 工具调用（Agent） | 模型按 Tool Schema **自主选择**（禁 if-else）；员工/考勤/订单/时间/知识库 |
| 4 | 📱 IM 集成（钉钉） | 群聊 @/私聊、验签、多轮上下文、引用展示、异常兜底 |
| 5 | 🖥 Web 管理后台 | 文档管理 + 对话日志 + 系统设置 + 调试聊天 |
| 6 | 🛡 工程化 | 一条命令启动、配置外置、logs/ 日志、错误兜底、16 条测试 |

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.12+ · FastAPI · Pydantic v2 · SQLAlchemy 2.x(async) · Alembic · uv |
| 数据库 | PostgreSQL 16 + pgvector · Redis 7 |
| 前端 | Next.js 16 · React 19 · TypeScript · Tailwind CSS v4 · pnpm |
| AI | OpenAI-compatible LLM · Embedding · RAG · 自研 Tool Calling Agent |
| 部署 | Docker Compose |

## 🏗 系统架构

```
IM Webhook / Web 调试页
  → IM Adapter（验签 → 解析 → IMMessage）
  → Chat Service（会话管理 + 异常兜底）
  → Agent（LLM 按 Tool Schema 自主选工具，max 3 轮）
      ├── search_knowledge_base → pgvector 检索（阈值 0.72 拒答）
      ├── get_employee / get_attendance / get_orders → Mock API (/mock-api/*)
      └── get_current_time → 通用工具
  → 引用 + 回复（Markdown）→ 落库 messages / tool_call_logs
trace_id 贯穿全链路。
```

## 🚀 本地启动

```bash
cp .env.example .env          # 填入真实 LLM_API_KEY / DINGTALK_*（骨架阶段可暂用占位值）
./scripts/start.sh            # docker compose up --build（4 服务）
./scripts/migrate.sh          # alembic upgrade head
./scripts/seed.sh             # 生成 docx 样本（md/txt 已内置）
curl http://localhost:8000/health   # {"status":"ok","service":"xiaosu-api"}
```

| 服务 | 地址 |
|------|------|
| API | http://localhost:8000 |
| Web 后台 | http://localhost:3001（首页跳转 /admin）|
| Postgres | localhost:5433（避开本机 5432）|
| Redis | localhost:6380（避开本机 6379）|

> 端口已避开本机常用端口。配置真实 `LLM_API_KEY`/`EMBEDDING_API_KEY` 后为真实语义检索；未配置时走确定性 mock，可独立验证全流程。

## 🔑 环境变量

见 [`.env.example`](./.env.example)。安全红线：API Key 不入库、不打印日志、设置页只显示「已配置/未配置」。

## 📱 钉钉机器人配置

1. 钉钉开放平台 → 创建企业内部应用/机器人，获取 `AppKey`/`AppSecret`/`RobotCode`
2. 配置消息接收地址为公网回调（如 ngrok）：`https://<your-domain>/api/im/dingtalk/callback`
3. 填入 `.env` 的 `DINGTALK_*`
4. 在群里 @ 机器人提问

## 🧪 自动化测试

```bash
cd apps/api && uv run pytest     # 16 条（解析/工具/IM/健康检查）
```

不依赖真实 API Key 与数据库（mock LLM + mock embedding）。

## 📋 验收问题自测

| 类型 | 问题 | 预期 |
|------|------|------|
| 知识库 | 员工每年有几天年假？ | 命中员工手册，带引用 |
| 知识库 | 报销发票需要什么材料？ | 命中员工手册 |
| 工具 | 员工 001 是哪个部门的？ | get_employee → 研发部 |
| 工具 | 上周一共多少订单？ | get_orders |
| 工具 | 现在几点？ | get_current_time |
| 多轮 | 他上周来上班几天？ | 指代消解 → get_attendance |
| 拒答 | CEO 的家庭住址？ | 隐私拒答 |
| 拒答 | 2030 年销售目标？ | 无依据拒答 |
| 鲁棒 | 无效 API Key | 友好兜底，不 500 |

## 📈 Roadmap

| 阶段 | 状态 |
|------|------|
| 0 项目准备 | ✅ |
| 1 工程骨架 | ✅ |
| 2 数据模型 | ✅ |
| 3 文档知识库 | ✅ |
| 4 RAG 问答 | ✅ |
| 5 工具调用 | ✅ |
| 6 IM 集成 | ✅ |
| 7 Web 后台 | ✅ |
| 8 鲁棒性 | ✅ |
| 9 自动化测试 | ✅ |
| 10 交付文档 | ✅ |

## 📚 相关文档

- [`招聘笔试题.html`](./招聘笔试题.html) · [`开发规范.md`](./开发规范.md) · [`AI 助手开发文档.md`](./AI%20助手开发文档.md) · [`小苏 AI 助手分阶段开发文档.md`](./小苏%20AI%20助手分阶段开发文档.md)
- [`AI_USAGE.md`](./AI_USAGE.md) — AI Coding 使用过程
