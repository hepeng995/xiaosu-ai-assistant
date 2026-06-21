"""MCP 运行时：复用现有 Chat Service、Tool 与文档服务。"""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from app.agents.tool_registry import execute_tool
from app.core.errors import ErrorCode
from app.core.observability import trace_id_var
from app.db.session import AsyncSessionLocal
from app.models import DocumentChunk
from app.services import chat_service, document_service
from app.services.retrieval_service import search_knowledge
from app.tools.base import BaseTool, ToolResult

_TOOL_UNAVAILABLE = "小苏暂时无法连接内部系统，请稍后再试。"
_KNOWLEDGE_UNAVAILABLE = "小苏暂时无法检索知识库，请稍后再试或联系管理员。"
_UNKNOWN_UNAVAILABLE = "小苏遇到了一点问题，已记录日志，请稍后再试。"
_CHUNK_PREVIEW_LEN = 240


def _trace_id() -> str:
    return f"trace_mcp_{uuid.uuid4().hex[:16]}"


async def _with_trace(event: str, fn: Callable[[], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
    trace_id = _trace_id()
    token = trace_id_var.set(trace_id)
    with logger.contextualize(trace_id=trace_id):
        mcp_logger = logger.bind(module="mcp", event=event)
        mcp_logger.info("MCP 调用开始")
        try:
            result = await fn()
            result.setdefault("trace_id", trace_id)
            mcp_logger.info("MCP 调用完成 success={}", result.get("success", True))
            return result
        except Exception as exc:
            mcp_logger.exception("MCP 调用失败: {}", exc)
            return {
                "success": False,
                "error_code": ErrorCode.UNKNOWN_ERROR,
                "message": _UNKNOWN_UNAVAILABLE,
                "trace_id": trace_id,
            }
        finally:
            trace_id_var.reset(token)


def _tool_failure_message(result: ToolResult) -> str:
    error = result.error_message or ""
    if "不存在" in error or "缺少" in error:
        return error
    return _TOOL_UNAVAILABLE


def _tool_payload(result: ToolResult) -> dict[str, Any]:
    if result.success:
        return {"success": True, "data": result.data}
    return {
        "success": False,
        "error_code": result.error_code or ErrorCode.TOOL_ERROR,
        "message": _tool_failure_message(result),
    }


async def chat(
    message: str,
    conversation_id: str = "default",
    user_id: str = "mcp_user",
    user_name: str | None = None,
) -> dict[str, Any]:
    """以 MCP 平台身份调用小苏完整问答主链路。"""

    async def _run() -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            result = await chat_service.chat(
                "mcp",
                conversation_id,
                user_id,
                message,
                session,
                user_name,
            )
            return {"success": True, **result}

    return await _with_trace("mcp_chat", _run)


async def search_knowledge_base(query: str, top_k: int | None = None) -> dict[str, Any]:
    """直接检索知识库，返回可溯源引用结果。"""

    async def _run() -> dict[str, Any]:
        try:
            async with AsyncSessionLocal() as session:
                results = await search_knowledge(query, session, top_k=top_k)
        except Exception as exc:
            logger.warning("MCP 知识库检索失败: {}", exc)
            return {
                "success": False,
                "error_code": ErrorCode.VECTOR_DB_ERROR,
                "message": _KNOWLEDGE_UNAVAILABLE,
                "results": [],
            }
        return {"success": True, "results": results}

    return await _with_trace("mcp_search_knowledge_base", _run)


async def run_tool(tool: BaseTool, arguments: dict[str, Any]) -> dict[str, Any]:
    """执行现有 BaseTool，并统一 MCP 侧错误输出。"""

    async def _run() -> dict[str, Any]:
        try:
            result = await execute_tool(tool, arguments)
        except Exception as exc:
            logger.warning("MCP 工具执行失败 tool={} err={}", tool.name, exc)
            result = ToolResult(
                success=False,
                error_code=ErrorCode.TOOL_ERROR,
                error_message=_TOOL_UNAVAILABLE,
            )
        return _tool_payload(result)

    return await _with_trace(f"mcp_tool_{tool.name}", _run)


async def list_documents_resource() -> dict[str, Any]:
    """列出 MCP resource 暴露的知识库文档。"""

    async def _run() -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            documents = await document_service.list_documents(session)
            return {
                "success": True,
                "items": [
                    {
                        "id": str(doc.id),
                        "filename": doc.original_filename,
                        "status": doc.status,
                        "version": doc.version,
                        "created_at": doc.created_at.isoformat()
                        if doc.created_at is not None
                        else None,
                    }
                    for doc in documents
                ],
            }

    return await _with_trace("mcp_documents_resource", _run)


def _chunk_item(chunk: DocumentChunk) -> dict[str, Any]:
    content = chunk.content or ""
    return {
        "id": str(chunk.id),
        "document_id": str(chunk.document_id),
        "chunk_index": chunk.chunk_index,
        "heading_path": chunk.heading_path,
        "page_number": chunk.page_number,
        "paragraph_index": chunk.paragraph_index,
        "content_preview": content[:_CHUNK_PREVIEW_LEN],
    }


async def list_document_chunks_resource(document_id: str) -> dict[str, Any]:
    """列出指定文档的未删除分块。"""

    async def _run() -> dict[str, Any]:
        try:
            doc_uuid = uuid.UUID(document_id)
        except ValueError:
            return {
                "success": False,
                "error_code": ErrorCode.DOCUMENT_PARSE_ERROR,
                "message": "document_id 不是有效 UUID",
                "items": [],
            }
        async with AsyncSessionLocal() as session:
            chunks = await document_service.list_chunks(doc_uuid, session)
            return {"success": True, "items": [_chunk_item(chunk) for chunk in chunks]}

    return await _with_trace("mcp_document_chunks_resource", _run)
