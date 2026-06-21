"""官方 MCP SDK 入口：注册小苏 tools/resources，并支持 stdio 运行。"""

import json
from typing import Any

from app.core.config import settings
from app.mcp import runtime
from app.tools.attendance_tool import AttendanceTool
from app.tools.employee_tool import EmployeeTool
from app.tools.orders_tool import OrdersTool
from app.tools.time_tool import CurrentTimeTool


def _create_fastmcp() -> Any:
    """创建 FastMCP 实例；HTTP 场景下让父应用控制挂载路径。"""
    from mcp.server.fastmcp import FastMCP

    try:
        return FastMCP(settings.MCP_SERVER_NAME, streamable_http_path="/")
    except TypeError:
        return FastMCP(settings.MCP_SERVER_NAME)


mcp_server = _create_fastmcp()


@mcp_server.tool()
async def xiaosu_chat(
    message: str,
    conversation_id: str = "default",
    user_id: str = "mcp_user",
    user_name: str | None = None,
) -> dict[str, Any]:
    """调用小苏完整问答能力，保留 RAG 引用、工具调用和会话上下文。"""
    return await runtime.chat(message, conversation_id, user_id, user_name)


@mcp_server.tool()
async def xiaosu_search_knowledge_base(query: str, top_k: int | None = None) -> dict[str, Any]:
    """直接检索小苏知识库，返回可定位引用结果。"""
    return await runtime.search_knowledge_base(query, top_k)


@mcp_server.tool()
async def xiaosu_get_employee(employee_id: str) -> dict[str, Any]:
    """根据员工 ID 查询员工基础信息。"""
    return await runtime.run_tool(EmployeeTool(), {"employee_id": employee_id})


@mcp_server.tool()
async def xiaosu_get_attendance(
    employee_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """根据员工 ID 和日期范围查询考勤记录。"""
    return await runtime.run_tool(
        AttendanceTool(),
        {"employee_id": employee_id, "start_date": start_date, "end_date": end_date},
    )


@mcp_server.tool()
async def xiaosu_get_orders(start_date: str, end_date: str) -> dict[str, Any]:
    """根据日期范围查询历史订单记录。"""
    return await runtime.run_tool(OrdersTool(), {"start_date": start_date, "end_date": end_date})


@mcp_server.tool()
async def xiaosu_get_current_time(timezone: str = "Asia/Shanghai") -> dict[str, Any]:
    """查询当前日期与时间。"""
    return await runtime.run_tool(CurrentTimeTool(), {"timezone": timezone})


@mcp_server.resource("xiaosu://documents")
async def xiaosu_documents() -> str:
    """列出小苏知识库文档。"""
    return json.dumps(await runtime.list_documents_resource(), ensure_ascii=False)


@mcp_server.resource("xiaosu://documents/{document_id}/chunks")
async def xiaosu_document_chunks(document_id: str) -> str:
    """列出指定文档的知识库分块。"""
    data = await runtime.list_document_chunks_resource(document_id)
    return json.dumps(data, ensure_ascii=False)


def run_stdio() -> None:
    """stdio 模式入口，供 Claude Desktop / Cursor 本地启动。"""
    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    run_stdio()

