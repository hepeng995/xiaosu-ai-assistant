"""工具注册表：注册工具、输出 Tool Schema 给 LLM、按名查找并执行。"""

import asyncio
import time
import uuid
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ErrorCode
from app.db.session import AsyncSessionLocal
from app.models import ToolCallLog
from app.tools.attendance_tool import AttendanceTool
from app.tools.base import BaseTool, ToolResult
from app.tools.employee_tool import EmployeeTool
from app.tools.knowledge_tool import KnowledgeSearchTool
from app.tools.orders_tool import OrdersTool
from app.tools.time_tool import CurrentTimeTool


def default_tools(session: AsyncSession | None = None) -> list[BaseTool]:
    """返回默认工具集合（知识库工具需 session）。"""
    tools: list[BaseTool] = [
        EmployeeTool(),
        AttendanceTool(),
        OrdersTool(),
        CurrentTimeTool(),
    ]
    if session is not None:
        tools.append(KnowledgeSearchTool(session))
    return tools


def tools_schema(tools: list[BaseTool]) -> list[dict[str, Any]]:
    """输出 OpenAI function-calling 格式的 Tool Schema 列表。"""
    return [t.schema() for t in tools]


def find_tool(tools: list[BaseTool], name: str) -> BaseTool | None:
    """按工具名查找。"""
    for t in tools:
        if t.name == name:
            return t
    return None


async def execute_tool(
    tool: BaseTool,
    arguments: dict[str, Any],
    message_id: uuid.UUID | None = None,
) -> ToolResult:
    """执行工具并写入 tool_call_logs。"""
    tool_logger = logger.bind(module="tool", event="tool_call", tool_name=tool.name)
    start = time.time()
    try:
        result = await asyncio.wait_for(tool.run(arguments), timeout=settings.TOOL_TIMEOUT_SECONDS)
    except TimeoutError:
        result = ToolResult(
            success=False,
            error_code=ErrorCode.TOOL_TIMEOUT,
            error_message="工具调用超时",
        )
    except Exception as exc:
        result = ToolResult(
            success=False,
            error_code=ErrorCode.TOOL_ERROR,
            error_message="工具调用失败",
        )
        tool_logger.warning("工具执行异常: {}", exc)
    if not result.success and result.error_code is None:
        result.error_code = ErrorCode.TOOL_ERROR
    latency_ms = int((time.time() - start) * 1000)
    tool_logger.info("工具调用完成 success={} latency_ms={}", result.success, latency_ms)
    try:
        async with AsyncSessionLocal() as session:
            log_result = (
                result.data
                if result.success and isinstance(result.data, (dict, list))
                else {"error_code": result.error_code, "error_message": result.error_message}
            )
            session.add(
                ToolCallLog(
                    message_id=message_id,
                    tool_name=tool.name,
                    arguments=arguments,
                    result=log_result,
                    success=result.success,
                    error_message=result.error_message,
                    latency_ms=latency_ms,
                )
            )
            await session.commit()
    except Exception as exc:
        logger.warning("写入 tool_call_log 失败: {}", exc)
    return result
