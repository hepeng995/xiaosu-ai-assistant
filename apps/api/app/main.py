"""FastAPI 应用入口：装配中间件、异常处理与路由。"""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes_admin_documents import router as documents_router
from app.api.routes_admin_logs import router as admin_logs_router
from app.api.routes_admin_settings import router as admin_settings_router
from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.api.routes_im import dingtalk_router as im_dingtalk_router
from app.api.routes_im import feishu_router as im_feishu_router
from app.api.routes_mock_api import router as mock_api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.observability import trace_id_var


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：启动初始化日志 + 数据库连通性检查。"""
    from app.db.session import check_db_connection

    setup_logging()
    logger.info("应用启动 name={} env={}", settings.APP_NAME, settings.APP_ENV)
    db_ok = await check_db_connection()
    logger.info("数据库连通性: {}", "ok" if db_ok else "unavailable(将在实际查询时重试)")
    yield
    logger.info("应用关闭")


def create_app() -> FastAPI:
    """创建并装配 FastAPI 应用。"""
    app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)

    # CORS（开发期宽松；上线前按 IM/Web 域名收紧）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def trace_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """为每个请求生成唯一 trace_id，绑定到 loguru 上下文并写入响应头。"""
        trace_id = request.headers.get("x-trace-id") or f"trace_{uuid.uuid4().hex[:16]}"
        request.state.trace_id = trace_id
        with logger.contextualize(trace_id=trace_id):
            trace_id_var.set(trace_id)
            logger.info("请求开始 {} {}", request.method, request.url.path)
            response = await call_next(request)
            response.headers["x-trace-id"] = trace_id
            logger.info(
                "请求结束 {} {} status={}",
                request.method,
                request.url.path,
                response.status_code,
            )
            return response

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(documents_router)
    app.include_router(chat_router)
    app.include_router(mock_api_router)
    app.include_router(im_dingtalk_router)
    app.include_router(im_feishu_router)
    app.include_router(admin_logs_router)
    app.include_router(admin_settings_router)
    if settings.MCP_HTTP_ENABLED:
        from app.mcp.http import get_mcp_http_app

        app.mount(settings.MCP_HTTP_PATH, get_mcp_http_app())
        logger.info("MCP HTTP 已挂载 path={}", settings.MCP_HTTP_PATH)
    return app


app = create_app()
