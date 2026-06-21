"""统一错误码与全局异常处理。

错误码沿用《AI 助手开发文档》第 17 节，禁止自由发挥。
所有异常统一返回 ``{success, error_code, message, trace_id}`` 结构。
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger


class ErrorCode:
    """业务错误码。"""

    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_AUTH_ERROR = "LLM_AUTH_ERROR"
    VECTOR_DB_ERROR = "VECTOR_DB_ERROR"
    DOCUMENT_PARSE_ERROR = "DOCUMENT_PARSE_ERROR"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    TOOL_ERROR = "TOOL_ERROR"
    IM_VERIFY_ERROR = "IM_VERIFY_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    # 管理后台鉴权（沿用 UPPER_SNAKE_CASE 风格，与现有错误码一致）
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_PERMISSION_DENIED = "AUTH_PERMISSION_DENIED"


class AppException(Exception):
    """业务异常，携带错误码、友好文案与 HTTP 状态码。"""

    def __init__(
        self,
        error_code: str = ErrorCode.UNKNOWN_ERROR,
        message: str = "小苏遇到了一点问题，已记录日志，请稍后再试。",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "-") or "-"


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器，确保任何异常都返回统一结构。"""

    @app.exception_handler(AppException)
    async def _handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        logger.warning("业务异常 code={} msg={}", exc.error_code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error_code": exc.error_code,
                "message": exc.message,
                "trace_id": _trace_id(request),
            },
        )

    @app.exception_handler(Exception)
    async def _handle_unknown(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未捕获异常: {}", exc)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error_code": ErrorCode.UNKNOWN_ERROR,
                "message": "小苏遇到了一点问题，已记录日志，请稍后再试。",
                "trace_id": _trace_id(request),
            },
        )
