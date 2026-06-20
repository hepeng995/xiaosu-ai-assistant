# 使用内置 Dockerfile frontend（避免从 Docker Hub 拉取 syntax 镜像，适配受限网络）
FROM python:3.12-slim

# 安装 uv（官方推荐：从 uv 镜像拷贝二进制）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# 先装依赖（利用层缓存：仅 pyproject/uv.lock 变化才重装）
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

# 再拷贝源码、迁移配置并完成安装
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --no-dev --no-install-project

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
