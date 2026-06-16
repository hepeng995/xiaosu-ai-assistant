"""IM 统一消息抽象（跨平台：钉钉/飞书/企微/Web）。"""

from typing import Any, Literal

from pydantic import BaseModel


class IMMessage(BaseModel):
    """统一入站消息（各 IM 平台解析后转换为此结构）。"""

    platform: Literal["dingtalk", "feishu", "wecom", "web"]
    message_id: str
    conversation_id: str
    conversation_type: Literal["group", "private", "web"]
    user_id: str
    user_name: str | None = None
    text: str
    raw: dict[str, Any]


class IMReply(BaseModel):
    """统一出站回复。"""

    text: str
    markdown: str | None = None
    references: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []


class IMVerifyError(Exception):
    """IM 验签失败异常。"""
