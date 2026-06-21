"""IM 统一消息抽象（跨平台：钉钉/飞书/企微/Web）。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class IMMention(BaseModel):
    """IM 消息里的 @ 成员信息，用于富消息展示。"""

    open_id: str = ""
    user_id: str = ""
    name: str = ""
    key: str = ""


class IMAttachment(BaseModel):
    """IM 附件元数据；实际文件内容由平台适配层按需下载。"""

    file_key: str
    filename: str
    file_size: int = 0
    file_type: str = ""


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
    mentions: list[IMMention] = Field(default_factory=list)
    attachments: list[IMAttachment] = Field(default_factory=list)


class IMReply(BaseModel):
    """统一出站回复。"""

    text: str
    markdown: str | None = None
    references: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class IMVerifyError(Exception):
    """IM 验签失败异常。"""
