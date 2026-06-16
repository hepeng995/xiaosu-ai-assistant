"""工具注册表：注册工具、输出 Tool Schema 给 LLM、按名查找并执行。"""

import time
import uuid
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

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
    start = time.time()
    result = await tool.run(arguments)
    latency_ms = int((time.time() - start) * 1000)
    try:
        async with AsyncSessionLocal() as session:
            session.add(
                ToolCallLog(
                    message_id=message_id,
                    tool_name=tool.name,
                    arguments=arguments,
                    result=result.data
                    if isinstance(result.data, (dict, list))
                    else {"text": result.data},
                    success=result.success,
                    error_message=result.error_message,
                    latency_ms=latency_ms,
                )
            )
            await session.commit()
    except Exception as exc:
        logger.warning("写入 tool_call_log 失败: {}", exc)
    return result
