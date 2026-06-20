# AI_USAGE.md

> 本项目全程使用 **Claude Code（GLM-5.2）** 协助开发。以下为真实的 AI Coding 过程记录，非套话。

## 1. 我使用了哪些 AI 工具

- **Claude Code**：全栈开发主力——架构搭建、代码生成、调试、测试、文档。
- **uv / pnpm / docker**：由 AI 指导使用，AI 负责生成配置与排错。

## 2. AI 用在哪些环节

架构设计、数据库模型、文档解析器、RAG/Agent 编排、IM 适配器、Web 后台、Docker 编排、自动化测试、调试所有环境问题（端口/换行/psycopg/pnpm）。

## 3. 一个具体 Prompt 示例

> "实现 Tool Calling Agent，不能用简单 if-else 写死工具选择。模型需基于 Tool Schema 自主调用工具。"

AI 生成了 `agents/agent.py`：把 5 个工具的 Schema 交给 LLM，由 LLM 的 `chat_with_tools`（function calling）返回 `tool_calls`，agent 执行后回填再生成。**可直接用**：agent 主循环零 if-else 路由。
**必须改**：无 API Key 时无法真实 function calling，AI 初版直接调真实 API 导致测试无法进行——我让它加了 `_mock_plan`（模拟 LLM 工具选择），才能在无 key 环境验证全流程。

## 4. AI 生成代码中可直接使用的部分

- pgvector 余弦检索 SQL、Alembic 迁移、FastAPI 路由骨架、Pydantic 模型——经 ruff/mypy/pytest 验证后直接采用。

## 5. 我手动修改的部分和原因

- **mock embedding 检索**：AI 初版 mock 向量是随机哈希，导致 RAG 检索无法命中"年假"。我让 retrieval 在 mock 模式改用**字符重叠近似检索**，无 key 时也能验证命中与拒答。
- **mock 阈值**：初版 0.3 太宽松，"2030 销售目标"误命中。我调到 0.5，无关问题正确拒答。

## 6. AI 把我带偏的一次经历

**port 冲突误判**：`docker compose up` 报 5432 占用，AI 一度建议改 DATABASE_URL 主机名。我发现是**宿主端口**映射冲突（非容器间），正确做法是改 `ports: "5433:5432"`。同理 3000/6379。修复后保留映射注释说明。

## 7. 我如何验证 AI 代码

- **单元测试**：27 条 pytest（解析/工具/IM 钉钉+飞书、审计增强、SSE 降级），不依赖真实 API。
- **端到端**：docker compose 起服务，curl 验证上传→indexed、年假命中带引用、员工部门选工具、多轮指代消解、无效 key 兜底。
- **静态检查**：ruff + mypy 每阶段全绿；密钥扫描 `git log -p | grep sk-`。
- **日志**：trace_id 贯穿，logs/app.log + error.log 可追溯。

## 8. 如果重做一次

- 更早引入真实 API Key 做一次真实 function calling 验证（当前代码已支持真实分支，但真实联调留给交付前手动验收）。
- IM 验证提前用钉钉/飞书沙箱（当前自动化测试覆盖 webhook 解析、验签、飞书解密与富文本格式化）。
- 前端用 shadcn/ui（当前纯 Tailwind，能用但不统一）。

## 9. 飞书 IM 渠道接入（迭代增强）

需求文档本就要求钉钉/飞书/企微三平台，项目设计时 `IMMessage.platform` 已预留 `"feishu"`，`chat_service` 用 `platform` 参数做会话隔离，故接入飞书是「复刻钉钉 + 适配飞书协议」，核心聊天/检索/Agent/落库链路零改动。

**关键决策（与 AI 对齐）**：
- 回复方式：主动调 `/im/v1/messages` 发消息（需 `app_id+app_secret` 换 `tenant_access_token`），而非被动响应——保证 IM 异常兜底逻辑与钉钉一致。
- 安全校验：完整实现 Encrypt Key 的 **AES-256-CBC 解密** + **X-Lark-Signature SHA256 验签** + **url_verification 握手**；未配置时开发放行+告警（对齐钉钉）。

**AI 协助点**：WebSearch 核实飞书最新协议（解密：SHA256(key) 前 32 字节作 AES key、IV 取密文前 16 字节；验签：SHA256(timestamp+nonce+key+body)）；生成 `im/feishu.py` 适配器、`format_feishu_post` 富文本、集中式 `routes_im.py`。

**踩坑（AI 协助排查）**：
- 钉钉路由迁移时日志行被压成单行触发 E501 → 恢复多行；
- `# noqa: BLE001` 多余（ruff 未启用 blind-except 规则）→ 删除；
- `conversation_type` mypy 报 Literal 不匹配 → 显式 `Literal["group","private","web"]` 标注；
- 群聊 `@_user_1` 占位剥离后残留前导空格 → `.strip()`；
- `api/` 目录原已 8 文件，再加会破红线 → IM 路由集中到 `routes_im.py`。

## 10. 增强亮点收口（本轮）

本轮按作品要求补了几处“面试容易追问”的点：

- **chunk 软删除**：同名替换/重索引不再物理删除旧分块，而是 `deleted_at` 停用；检索 SQL 默认过滤旧 chunk。
- **工具审计**：assistant 消息先落库，再把 `message_id` 传给 Agent，`tool_call_logs` 能追到具体回答。
- **错误码落库**：Agent/LLM 异常回填 `LLM_AUTH_ERROR` / `LLM_TIMEOUT` / `UNKNOWN_ERROR`，工具失败映射 `TOOL_TIMEOUT` / `TOOL_ERROR`。
- **分文件日志**：新增 `llm.log` / `im.log` / `indexing.log` / `tool.log`，不记录明文密钥和完整长 Prompt。
- **可观测性预留**：增加 Langfuse 配置开关，未配置时 noop；真实 key 联调仍由交付前手动执行。

## 关键踩坑（AI 协助排查）

| 问题 | 原因 | 解决 |
|------|------|------|
| psycopg async 失败 | Windows ProactorEventLoop | env.py 切 SelectorEventLoop |
| ruff B008 | Depends 作默认值 | extend-immutable-calls 豁免 |
| ruff RUF001/2/3 | 中文全角标点 | ignore 这三条 |
| ruff I001 | TYPE_CHECKING import 打乱排序 | ruff check --fix（format 不修）|
| pnpm ERR_PNPM_IGNORED_BUILDS | sharp 构建脚本 | pnpm-workspace.yaml allowBuilds |
| docker syntax 拉取超时 | BuildKit frontend | 移除 # syntax 指令 |
| seed.sh 路径错 | ../data 从 apps/api = apps/data | 改 ../../data |
