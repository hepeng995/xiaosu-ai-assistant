"""考勤工具：调用 Mock API /mock-api/attendance。"""

from typing import Any

from app.tools.base import ToolResult
from app.tools.internal_api import request_internal_api


class AttendanceTool:
    name = "get_attendance"
    description = "根据员工 ID 和日期范围查询考勤记录与出勤天数。"

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "employee_id": {"type": "string"},
                        "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                        "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                    },
                    "required": ["employee_id", "start_date", "end_date"],
                },
            },
        }

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        emp_id = str(arguments.get("employee_id", "")).strip()
        start_date = str(arguments.get("start_date", "")).strip()
        end_date = str(arguments.get("end_date", "")).strip()
        if not (emp_id and start_date and end_date):
            return ToolResult(success=False, error_message="缺少 employee_id/start_date/end_date")
        try:
            resp = await request_internal_api(
                "/mock-api/attendance",
                params={"employee_id": emp_id, "start_date": start_date, "end_date": end_date},
            )
            if resp.status_code >= 400:
                return ToolResult(
                    success=False,
                    error_message=f"考勤查询失败: HTTP {resp.status_code}",
                )
            return ToolResult(success=True, data=resp.data)
        except Exception as exc:
            return ToolResult(success=False, error_message=f"考勤查询失败: {exc}")
