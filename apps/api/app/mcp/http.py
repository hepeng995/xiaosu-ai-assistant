"""MCP Streamable HTTP 挂载与 Bearer Token 鉴权。"""

from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.core.config import settings
from app.core.errors import ErrorCode


class McpHttpAuthApp:
    """轻量 ASGI 包装器：给 MCP HTTP transport 加 Bearer Token 校验。"""

    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self._app = app
        self._warned_dev_open = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._authorized(scope):
            await self._app(scope, receive, send)
            return
        response = JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error_code": ErrorCode.IM_VERIFY_ERROR,
                "message": "MCP HTTP 鉴权失败",
            },
        )
        await response(scope, receive, send)

    def _authorized(self, scope: Scope) -> bool:
        token_configured = settings.is_secret_configured(settings.MCP_HTTP_AUTH_TOKEN)
        if not token_configured and settings.is_dev:
            if not self._warned_dev_open:
                logger.warning("MCP HTTP 未配置鉴权 Token，开发环境临时放行")
                self._warned_dev_open = True
            return True
        if not token_configured:
            logger.warning("MCP HTTP 在非开发环境缺少鉴权 Token，拒绝访问")
            return False
        headers = dict(scope.get("headers") or [])
        raw_auth = headers.get(b"authorization", b"").decode("utf-8")
        return raw_auth == f"Bearer {settings.MCP_HTTP_AUTH_TOKEN}"


def get_mcp_http_app() -> Any:
    """返回官方 SDK 的 Streamable HTTP ASGI app，并套上鉴权。"""
    from app.mcp.server import mcp_server

    return McpHttpAuthApp(mcp_server.streamable_http_app())

