"""工具统一抽象（Protocol + 结果模型）。"""

from collections.abc import Callable, Coroutine
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class ToolResult(BaseModel):
    """工具执行结果。"""

    success: bool
    data: dict[str, Any] | list[Any] | str | None = None
    error_message: str | None = None
    error_code: str | None = None


@runtime_checkable
class BaseTool(Protocol):
    """工具接口：name / description / schema() / run()。"""

    name: str
    description: str

    def schema(self) -> dict[str, Any]: ...

    def run(self, arguments: dict[str, Any]) -> Coroutine[Any, Any, ToolResult]: ...


# 工具工厂类型
ToolFactory = Callable[[], BaseTool]
