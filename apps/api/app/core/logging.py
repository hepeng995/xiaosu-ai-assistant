"""日志配置：loguru 落盘到 ``logs/``，结构化字段含 ``trace_id``。

配置：控制台 + ``app.log`` / ``error.log``，并按 ``module`` 分流到
``llm.log`` / ``im.log`` / ``indexing.log`` / ``tool.log``。
"""

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from types import FrameType
from typing import Any

from loguru import logger

from app.core.config import settings

# 默认 extra，确保 format 中 {extra[trace_id]} 始终可解析
logger.configure(extra={"trace_id": "-"})

_LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
    "trace_id={extra[trace_id]} | "
    "{name}:{function}:{line} | {message}"
)


class _InterceptHandler(logging.Handler):
    """拦截标准库 logging，转发给 loguru，统一 uvicorn/sqlalchemy 日志。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame: FrameType | None = logging.currentframe()
        depth = 2
        while frame is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _module_filter(module_name: str) -> Callable[..., bool]:
    """生成 loguru sink filter，按 extra.module 分流。"""

    def _filter(record: Any) -> bool:
        return record["extra"].get("module") == module_name

    return _filter


def setup_logging() -> None:
    """初始化全局日志（应用启动时调用一次）。"""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()
    console_level = "DEBUG" if settings.is_dev else "INFO"

    # 控制台
    logger.add(
        sys.stdout,
        format=_LOG_FORMAT,
        level=console_level,
        backtrace=True,
        diagnose=settings.is_dev,
        enqueue=True,
    )

    # app.log：INFO 及以上
    logger.add(
        log_dir / "app.log",
        format=_LOG_FORMAT,
        level="INFO",
        rotation="10 MB",
        retention="14 days",
        encoding="utf-8",
        enqueue=True,
    )

    # error.log：ERROR 及以上
    logger.add(
        log_dir / "error.log",
        format=_LOG_FORMAT,
        level="ERROR",
        rotation="10 MB",
        retention="14 days",
        encoding="utf-8",
        enqueue=True,
    )

    for module_name, filename in (
        ("llm", "llm.log"),
        ("im", "im.log"),
        ("indexing", "indexing.log"),
        ("tool", "tool.log"),
    ):
        logger.add(
            log_dir / filename,
            format=_LOG_FORMAT,
            level="INFO",
            rotation="10 MB",
            retention="14 days",
            encoding="utf-8",
            enqueue=True,
            filter=_module_filter(module_name),
        )

    # 拦截标准 logging，让 uvicorn / sqlalchemy 的日志也走 loguru
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy", "fastapi"):
        logging.getLogger(name).handlers = [_InterceptHandler()]
