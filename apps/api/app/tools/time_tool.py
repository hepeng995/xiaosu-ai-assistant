"""当前时间工具（通用工具，不依赖外部 API）。"""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.tools.base import ToolResult


class CurrentTimeTool:
    name = "get_current_time"
    description = "查询当前日期与时间，可指定时区。"

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "description": "时区，例如 Asia/Shanghai",
                        }
                    },
                    "required": ["timezone"],
                },
            },
        }

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        tz_name = str(arguments.get("timezone", "Asia/Shanghai")).strip()
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("UTC")
            tz_name = "UTC"
        now = datetime.now(tz)
        return ToolResult(
            success=True,
            data={
                "timezone": tz_name,
                "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()],
            },
        )
