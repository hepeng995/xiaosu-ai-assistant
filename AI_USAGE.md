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

- **单元测试**：125 条 pytest（解析 / 工具选择 / IM 钉钉+飞书 / Agent 多轮回归 / 鉴权 / SSE 降级 / Mock LLM / 流式状态），不依赖真实 API。
- **端到端**：docker compose 起服务，curl 验证上传→indexed、年假命中带引用、员工部门选工具、多轮指代消解、无效 key 兜底。
- **静态检查**：ruff + mypy 每阶段全绿；密钥扫描 `git log -p | grep sk-`。
- **日志**：trace_id 贯穿，logs/app.log + error.log 可追溯。

## 8. 如果重做一次

- 更早引入真实 API Key 做一次真实 function calling 验证（当前代码已支持真实分支，但真实联调留给交付前手动验收）。
- IM 验证提前用钉钉/飞书沙箱（当前自动化测试覆盖 webhook 解析、验签、飞书解密与富文本格式化）。
- 更早把可观测性与 Evals 接到真实后端：埋点（trace_span/llm_span）与评测脚本已就绪，但全程走 noop / 结构验证；真实链路 trace 截图与答案语义准确率应与功能同步产出，而不是留到交付前补。

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
- **可观测性埋点**：Langfuse 已接入全链路（`trace_span` 覆盖 chat/retrieval/tool_call，`llm_span` 覆盖 LLM/embedding，均关联中间件注入的 `trace_id`）；未配置时 noop 降级，配置真实 `LANGFUSE_*` 后可在 Langfuse 面板看到完整请求链路。

## 11. 多轮 RAG 陷阱：同问题第二次问竟拒答（真实联调暴露 + AI 协助诊断）

**现象（真实联调复现）**：Web 调试页第一次问「竞业限制有多久」→ 正确回答 + 3 条引用；紧接着第二次问**完全相同**的问题 → 反而拒答「知识库没有找到相关内容」。同一问题同一知识库，结果不稳定，直接踩中评分红线（RAG 必带引用 + 稳定可复现）。

**根因（AI 协助逐层排查）**：
1. 先怀疑检索层不稳定——读 `retrieval_service._vector_search`：query 原文 embedding + pgvector 余弦，**同 query 必同结果**，排除。
2. 再看 `chat_service` 拒答判断：`not has_external_tool and not references → REFUSAL_NO_RESULT`。
3. 真正根因：第二轮 conversation 带着第一轮的完整答案 history，**真实 LLM 看到「已经答过了」就直接复述、不再调用 `search_knowledge_base`** → `references` 字段为空 → 误判拒答。这是 RAG 多轮的经典陷阱，单轮单测根本暴露不了。

**为什么 AI 生成的测试没覆盖**：既有测试全是「空 history + 单轮」，AI 也不会主动想到「同问题连问两次」这个反直觉场景——这正是 AI 生成测试的盲区，**必须靠真实联调才能暴露**。

**修复（双管齐下，commit 83c5191）**：
- Prompt 层：SYSTEM_PROMPT 加**铁律 8**「每次回答知识库问题都必须重新检索，引用必须反映本次检索」。
- 工程兜底：`agent.py` 主循环**第一轮空 tool_calls 时追加 `RETRIEVAL_NUDGE`** 让 LLM 重新检索（仅 `_round==0` 触发一次，不死循环；LLM 仍自主决策，不碰「工具选择禁硬编码」红线）。

**验证**：新增 `test_agent_multiturn_regression` 3 条（nudge 触发 / 不误伤正常流程 / 只 nudge 一次不死循环）+ 全量通过（用例数随迭代已增至 125 条）；真实环境连问两次确认第二次也带引用。

**复盘**：RAG 的多轮测试**必须覆盖「重复提问」「追问改写」**两类场景，不能只靠 prompt 约束 LLM——必须有工程兜底；这个 bug 只在真实 LLM + 真实 history 下才暴露，再次印证「真实联调不可省」。

## 12. 同一问题 Web 与飞书回答不一致：LLM 改写检索 query 导致（真实联调暴露 + AI 协助诊断）

**现象（真实联调复现）**：用户在 Web 调试页问「新人入职第一天要做哪些事？」→ 正确回答 + 3 条引用；**同一个问题在飞书问却拒答**（「没有找到关于『新人入职第一天安排』的相关文档」）。两个渠道走的是同一套 `chat_service` 主链路、同一个知识库，结果却分裂，直接影响「RAG 稳定可复现」评分项。

**根因（AI 协助查 tool_call_logs 取证）**：
1. 查 `tool_call_logs` 表对比两次检索：Web 的 LLM 改写出 query「新人入职第一天**要做哪些事**」，命中 5 条、top score **0.7643**；飞书的 LLM 改写出 query「新人入职第一天**流程**」，命中 3 条、top score **0.6950**（跌破 0.72 质量线）。
2. 飞书的低分 chunk 虽然返回给了 LLM，但语义偏离，LLM 判定「不相关」→ 自行生成自然语言拒答（不是系统 `REFUSAL_NO_RESULT` 模板，更难察觉）。
3. **为什么 query 不同**：`chat_with_tools` 的 `arguments.query` 由 LLM 按 function calling 自主生成，mimo-v2.5 在不同会话上下文（Web 会话干净 vs 飞书会话历史长且杂）下改写出不同 query——这是 OpenAI-compatible 国产模型 function calling 不稳定的典型表现，也是「工具参数由 LLM 决定」设计的固有脆弱点。

**修复（commit b021bea）**：在 `agent.py` 加 `_augment_references_with_user_query`——当 LLM 改写的 query 命中 top score < `RAG_SCORE_THRESHOLD` 时，**用用户原话补检索一次**，按 `chunk_id` 去重合并、按 score 降序。LLM query 高质量命中时直接返回（零额外成本）。接进 `prepare_response` 与 `prepare_response_stream` 两处 references 收集，Web/IM 路径一致。**不碰「工具选择禁硬编码」红线**——只是对检索结果做兜底增强，工具仍由 LLM 自主调用。

**验证**：新增 `test_augment_*` 3 条（高质量不补检索 / 低质量补检索合并去重 / 无原话直返）+ 全量 139 passed；飞书复测同问题不再拒答。

**复盘**：RAG 的检索稳定性**不能完全交给 LLM 的 query 改写**——LLM 改写有随机性、且随会话上下文漂移，必须用「用户原话」作为兜底检索词（hybrid: LLM query + user query）。这类「同输入不同渠道结果不一致」的 bug，只有在多渠道真实联调时才暴露，单渠道单测永远发现不了。

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
