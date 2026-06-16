"""文档相关出参模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    """文档信息（列表/上传响应）。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    status: str
    version: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int


class ChunkOut(BaseModel):
    """文档分块（含引用定位信息）。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chunk_index: int
    content: str
    heading_path: str | None
    page_number: int | None
    paragraph_index: int | None
