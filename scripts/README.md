# scripts/ · 统一脚本目录

> 本目录统一存放启动 / 测试 / lint / 迁移 / 种子等脚本，禁止散落临时命令。
> 所有脚本均为 bash（`set -e` 失败即终止），Windows 上请通过 Git Bash / WSL 执行。

| 脚本 | 用途 | 计划阶段 |
|------|------|----------|
| `start.sh` | `docker compose up --build`，启动全部服务 | 第 1 阶段 |
| `test.sh` | 后端 `uv run pytest`；前端 `pnpm test` | 第 1 / 9 阶段 |
| `lint.sh` | 后端 `uv run ruff check .`(+ `mypy`)；前端 `pnpm lint` | 第 1 阶段 |
| `migrate.sh` | `cd apps/api && uv run alembic upgrade head` | 第 2 阶段 |
| `seed.sh` | 写入种子数据（样本文档 / Mock 数据 / 示例会话） | 第 3 阶段 |

> ⚠️ 这些 `.sh` 文件将在对应阶段逐步创建，当前为空目录占位。
