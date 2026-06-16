"""聊天相关请求/响应模型。"""

from pydantic import BaseModel, Field


class Reference(BaseModel):
    """引用来源（可定位到文件/章节/段落）。"""

    document_id: str
    chunk_id: str
    filename: str
    heading_path: str | None = None
    page_number: int | None = None
    paragraph_index: int | None = None
    quote: str
    score: float


class ChatRequest(BaseModel):
    """聊天请求（含会话隔离维度）。"""

    platform: str = "web"
    conversation_id: str = "debug"
    user_id: str = "admin"
    user_name: str | None = None
    message: str = Field(..., min_length=1)


class ToolCallInfo(BaseModel):
    name: str
    arguments: dict


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    answer: str
    references: list[Reference] = []
    tool_calls: list[ToolCallInfo] = []
    usage: Usage = Usage()
    refused: bool = False
