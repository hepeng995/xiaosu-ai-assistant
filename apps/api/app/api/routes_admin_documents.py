"""文档管理 API：上传 / 列表 / 删除 / 查看分块 / 重新索引。"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppException, ErrorCode
from app.db.session import get_db
from app.models import Document, DocumentChunk
from app.schemas.document import ChunkOut, DocumentListOut, DocumentOut
from app.services import document_service
from app.services.indexing_service import index_document

router = APIRouter(prefix="/api/admin/documents", tags=["documents"])


@router.post("", response_model=DocumentOut)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
) -> DocumentOut:
    """上传文档，返回 pending；索引在后台任务中执行。"""
    doc = await document_service.upload_document(file, session)
    background_tasks.add_task(index_document, doc.id)
    return DocumentOut.model_validate(doc)


@router.get("", response_model=DocumentListOut)
async def list_documents(session: AsyncSession = Depends(get_db)) -> DocumentListOut:
    """列出未删除的文档。"""
    docs = await document_service.list_documents(session)
    items = [DocumentOut.model_validate(d) for d in docs]
    return DocumentListOut(items=items, total=len(items))


@router.delete("/{document_id}")
async def delete_document(
    document_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> dict[str, bool]:
    """软删除文档（不再参与检索）。"""
    ok = await document_service.soft_delete_document(document_id, session)
    return {"success": ok}


@router.get("/{document_id}/chunks", response_model=list[ChunkOut])
async def list_chunks(
    document_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> list[ChunkOut]:
    """查看文档分块（含引用定位信息）。"""
    chunks = await document_service.list_chunks(document_id, session)
    return [ChunkOut.model_validate(c) for c in chunks]


@router.post("/{document_id}/reindex", response_model=DocumentOut)
async def reindex_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
) -> DocumentOut:
    """清除旧分块并重新索引。"""
    doc = await session.get(Document, document_id)
    if doc is None or doc.deleted_at is not None:
        raise AppException(ErrorCode.DOCUMENT_PARSE_ERROR, "文档不存在或已删除", 404)
    await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    doc.status = "pending"
    doc.error_message = None
    await session.commit()
    await session.refresh(doc)
    background_tasks.add_task(index_document, doc.id)
    return DocumentOut.model_validate(doc)
