"""知识库检索工具：供 Agent 在需要查询公司制度时调用。"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.base import ToolResult


class KnowledgeSearchTool:
    """知识库检索工具（直接复用 retrieval_service，需注入 session）。"""

    name = "search_knowledge_base"
    description = "查询公司制度、员工手册、FAQ、入职指南、报销制度、考勤制度等知识库内容。"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "需要检索的问题"}},
                    "required": ["query"],
                },
            },
        }

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        from app.services.retrieval_service import search_knowledge

        query = str(arguments.get("query", "")).strip()
        if not query:
            return ToolResult(success=False, error_message="缺少 query")
        items = await search_knowledge(query, self._session)
        if not items:
            return ToolResult(success=True, data={"results": [], "message": "知识库无相关内容"})
        return ToolResult(success=True, data={"results": items})
