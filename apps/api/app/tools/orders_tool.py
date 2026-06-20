"""订单工具：调用 Mock API /mock-api/orders。"""

from typing import Any

from app.tools.base import ToolResult
from app.tools.internal_api import request_internal_api


class OrdersTool:
    name = "get_orders"
    description = "根据日期范围查询订单数据，可统计订单数量与销售额。"

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                        "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                    },
                    "required": ["start_date", "end_date"],
                },
            },
        }

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        start_date = str(arguments.get("start_date", "")).strip()
        end_date = str(arguments.get("end_date", "")).strip()
        if not (start_date and end_date):
            return ToolResult(success=False, error_message="缺少 start_date/end_date")
        try:
            resp = await request_internal_api(
                "/mock-api/orders",
                params={"start_date": start_date, "end_date": end_date},
            )
            if resp.status_code >= 400:
                return ToolResult(
                    success=False,
                    error_message=f"订单查询失败: HTTP {resp.status_code}",
                )
            return ToolResult(success=True, data=resp.data)
        except Exception as exc:
            return ToolResult(success=False, error_message=f"订单查询失败: {exc}")
