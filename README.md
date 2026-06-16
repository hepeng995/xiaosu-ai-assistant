# 小苏 AI 助手（Xiaosu AI Assistant）

> 公司内部 AI 助手「小苏」：员工在钉钉里 @ 机器人提问，系统基于 **RAG 知识库**回答（**带引用、可拒答**），并通过**自研 Tool Calling 编排层**调用内部 Mock API 工具；管理员通过 **Web 后台**管理文档、查看对话日志与 Token 消耗。

## 📌 项目状态

> 本项目当前处于**设计完成、开发启动**阶段，严格按 `小苏 AI 助手分阶段开发文档.md` 的 11 个阶段（第 0–10 阶段）推进。下方功能为**规划目标**，逐阶段交付。

## ✨ 核心功能（规划）

| # | 功能 | 说明 |
|---|------|------|
| 1 | 📚 文档知识库 | 上传 md/pdf/docx/txt，解析→分块→向量化→pgvector 入库；列表/删除/同名替换 |
| 2 | 💬 智能问答（RAG） | 基于知识库回答，**答案必须带引用**（文件名 + 段落/页码），无依据**必须拒答**；多轮对话 + 流式输出 |
| 3 | 🔧 工具调用（Agent） | 模型按 Tool Schema **自主选择**工具（禁 if-else 硬编码）；员工/考勤/订单/时间/知识库检索 |
| 4 | 📱 IM 集成（钉钉） | 群聊 @ 与私聊、多轮上下文、引用展示、异常兜底（核心验收入口） |
| 5 | 🖥 Web 管理后台 | 文档管理 + 对话日志 + 系统设置 + 调试聊天页（能用为主） |
| 6 | 🛡 工程化 | 一条命令启动、配置外置、`logs/` 日志、错误兜底、≥3 条自动化测试 |

## 🛠 技术栈（方案一，固定）

| 层 | 技术 |
|----|------|
| 后端 | Python 3.12+ · FastAPI · Pydantic v2 · SQLAlchemy 2.x · Alembic · uv（禁 pip） |
| 数据库 | PostgreSQL 16 + pgvector · Redis 7 |
| 前端 | Next.js 15.4+ · React 19+ · TypeScript · Tailwind CSS v4 · shadcn/ui · pnpm（禁 npm/yarn） |
| AI | OpenAI-compatible LLM · Embedding · RAG · 自研 Tool Calling Agent |
| 部署 | Docker Compose |
| 日志 | loguru → `logs/*.log` |

## 🏗 系统架构（文字版）

```
IM Webhook / Web 调试页
  → IM Adapter（验签 → 解析 → IMMessage）
  → Chat Service（会话管理 + 日志 + token 统计）
  → Conversation Memory（上下文 / 指代消解）
  → Agent Router（将 Tool Schema 交给 LLM，LLM 自主选择工具）
      ├── search_knowledge_base → Retrieval Service → pgvector
      ├── get_employee / get_attendance / get_orders → Mock API (/mock-api/*)
      └── get_current_time → 通用工具
  → 工具结果回填 LLM → 最终回答 + 引用
  → 写 messages / tool_call_logs，格式化为 IMReply 回复
```

> `trace_id` 贯穿从 IM 回调到 DB 日志的整条链路。完整架构图将在后续阶段补图。

## 🚀 本地启动

> ⚠️ **本节将在第 1 阶段（基础工程骨架）完成后补全可运行步骤。** 计划命令如下：

```bash
# 1. 准备环境变量
cp .env.example .env   # 填入真实 LLM_API_KEY / DINGTALK_* 等

# 2. 一键启动（PostgreSQL + pgvector + Redis + API + Web）
./scripts/start.sh     # 等价于 docker compose up --build

# 3. 数据库迁移
./scripts/migrate.sh

# 4. 健康检查
curl http://localhost:8000/health   # {"status":"ok","service":"xiaosu-api"}
# 前端：http://localhost:3000
```

## 🔑 环境变量

全部走环境变量（Pydantic Settings 读取），完整清单见 [`.env.example`](./.env.example)。关键项：`DATABASE_URL` / `REDIS_URL` / `LLM_*` / `EMBEDDING_*` / `RAG_*` / `DINGTALK_*`。

**安全红线**：API Key / App Secret 不入库、不打印到日志、Web 设置页只展示「已配置/未配置」。

## 🧪 自动化测试

> 将在第 9 阶段完成：≥3 条测试，其中 ≥1 条使用 Mock LLM（不依赖真实 API Key），覆盖文档索引、RAG 拒答、工具调用、IM Adapter。

```bash
./scripts/test.sh    # 后端 uv run pytest；前端 pnpm test
```

## 📈 Roadmap（分阶段进度）

| 阶段 | 名称 | 状态 |
|------|------|------|
| 0 | 项目准备与规范 | 🟡 进行中 |
| 1 | 基础工程骨架 | ⬜ 未开始 |
| 2 | 数据模型与公共能力 | ⬜ 未开始 |
| 3 | 文档知识库 | ⬜ 未开始 |
| 4 | RAG 智能问答 | ⬜ 未开始 |
| 5 | 工具调用 + Mock API | ⬜ 未开始 |
| 6 | ⭐ IM 集成（钉钉） | ⬜ 未开始 |
| 7 | Web 管理后台 | ⬜ 未开始 |
| 8 | 工程化与鲁棒性 | ⬜ 未开始 |
| 9 | 自动化测试 | ⬜ 未开始 |
| 10 | 文档与交付 | ⬜ 未开始 |

## 📚 相关文档

- [`招聘笔试题.html`](./招聘笔试题.html) — 需求源头与评分依据（最高优先级）
- [`AI 助手开发文档.md`](./AI%20助手开发文档.md) — 详细技术设计（架构/表结构/API/Prompt）
- [`小苏 AI 助手分阶段开发文档.md`](./小苏%20AI%20助手分阶段开发文档.md) — 11 阶段开发计划
- [`开发规范.md`](./开发规范.md) — 强制执行规范（技术栈红线/编码/安全/测试/Git）
- [`AI_USAGE.md`](./AI_USAGE.md) — AI Coding 使用过程（重要评分项）

## 📄 License

待定（个人笔试项目，代码归开发者所有）。
