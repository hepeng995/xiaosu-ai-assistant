"""文档服务：上传（含安全校验与同名替换）、列表、删除、重索引。"""

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import UploadFile
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppException, ErrorCode
from app.models import Document, DocumentChunk
from app.parsers import SUPPORTED_EXTENSIONS


def sanitize_filename(name: str) -> str:
    """提取纯文件名，去除路径穿越与危险字符（保留中文/字母/数字/._-）。"""
    base = name.replace("\\", "/").split("/")[-1]
    cleaned = "".join(c for c in base if c.isalnum() or c in "._- 、-")
    return cleaned.strip(". ") or "upload"


async def upload_document(file: UploadFile, session: AsyncSession) -> Document:
    """上传文档：校验 → 计算 hash → 同名替换 → 落盘 → 建 pending 记录。"""
    original = sanitize_filename(file.filename or "upload")
    ext = Path(original).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise AppException(
            ErrorCode.DOCUMENT_PARSE_ERROR,
            f"不支持的文件类型 {ext}（支持 {sorted(SUPPORTED_EXTENSIONS)}）",
            400,
        )

    content = await file.read()
    if len(content) > settings.UPLOAD_MAX_SIZE_BYTES:
        raise AppException(ErrorCode.DOCUMENT_PARSE_ERROR, "文件超过大小限制", 413)
    if not content:
        raise AppException(ErrorCode.DOCUMENT_PARSE_ERROR, "文件为空", 400)

    file_hash = hashlib.sha256(content).hexdigest()

    # 同名替换：旧文档软删除 + 旧 chunks 标记停用（不再参与检索）
    version = 1
    existing_result = await session.execute(
        select(Document).where(
            Document.original_filename == original, Document.deleted_at.is_(None)
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        version = existing.version + 1
        existing.status = "deleted"
        existing.deleted_at = datetime.now(UTC)
        await session.execute(
            update(DocumentChunk)
            .where(DocumentChunk.document_id == existing.id, DocumentChunk.deleted_at.is_(None))
            .values(deleted_at=datetime.now(UTC))
        )
        logger.info("同名替换: {} v{} → v{}", original, existing.version, version)

    stored_name = f"{uuid.uuid4().hex}{ext}"
    storage_dir = Path(settings.STORAGE_DIR)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / stored_name
    storage_path.write_bytes(content)

    doc = Document(
        filename=stored_name,
        original_filename=original,
        file_type=ext.lstrip("."),
        file_size=len(content),
        file_hash=file_hash,
        status="pending",
        version=version,
        storage_path=str(storage_path),
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    logger.info("文档已上传 doc={} original={} v{}", doc.id, original, version)
    return doc


async def list_documents(session: AsyncSession) -> list[Document]:
    """列出未删除的文档（按创建时间倒序）。"""
    result = await session.execute(
        select(Document).where(Document.deleted_at.is_(None)).order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def soft_delete_document(document_id: uuid.UUID, session: AsyncSession) -> bool:
    """软删除文档：置 deleted_at + status=deleted；对应 chunks 不再参与检索。"""
    doc = await session.get(Document, document_id)
    if doc is None or doc.deleted_at is not None:
        return False
    deleted_at = datetime.now(UTC)
    doc.status = "deleted"
    doc.deleted_at = deleted_at
    await session.execute(
        update(DocumentChunk)
        .where(DocumentChunk.document_id == doc.id, DocumentChunk.deleted_at.is_(None))
        .values(deleted_at=deleted_at)
    )
    await session.commit()
    logger.info("文档已软删除 doc={}", document_id)
    return True


async def list_chunks(document_id: uuid.UUID, session: AsyncSession) -> list[DocumentChunk]:
    """列出文档的分块（按 chunk_index）。"""
    result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id, DocumentChunk.deleted_at.is_(None))
        .order_by(DocumentChunk.chunk_index)
    )
    return list(result.scalars().all())
