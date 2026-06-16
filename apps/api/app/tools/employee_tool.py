"""员工信息工具：调用 Mock API /mock-api/employees/{id}。"""

from typing import Any

import httpx

from app.core.config import settings
from app.tools.base import ToolResult


class EmployeeTool:
    name = "get_employee"
    description = "根据员工 ID 查询员工姓名、部门、职级、主管等基础信息。"

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "employee_id": {"type": "string", "description": "员工编号，例如 001"}
                    },
                    "required": ["employee_id"],
                },
            },
        }

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        emp_id = str(arguments.get("employee_id", "")).strip()
        if not emp_id:
            return ToolResult(success=False, error_message="缺少 employee_id")
        base = f"http://localhost:{settings.APP_PORT}"
        try:
            async with httpx.AsyncClient(timeout=settings.TOOL_TIMEOUT_SECONDS) as client:
                resp = await client.get(f"{base}/mock-api/employees/{emp_id}")
            if resp.status_code == 404:
                return ToolResult(success=False, error_message=f"员工 {emp_id} 不存在")
            resp.raise_for_status()
            return ToolResult(success=True, data=resp.json())
        except Exception as exc:
            return ToolResult(success=False, error_message=f"员工查询失败: {exc}")
