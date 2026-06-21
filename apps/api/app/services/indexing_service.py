"""文档索引服务：解析 → 分块 → embedding → 写入 pgvector。"""

import uuid
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.llm.embedding import embedding_service
from app.models import Document, DocumentChunk
from app.parsers import get_parser
from app.parsers.base import ParsedBlock


@dataclass
class _ChunkData:
    content: str
    heading_path: str | None
    page_number: int | None
    paragraph_index: int | None
    chunk_index: int


def _embed_text(chunk: _ChunkData) -> str:
    """构建 embedding 文本：纳入 heading_path 让「指引性 FAQ」更易被语义命中。

    部分 chunk（尤其 FAQ 类）的 content 是简短答案，而 heading_path 才是与用户
    query 语义最接近的部分（如 heading="公司未来销售目标是多少？" 对应 query
    "2030 年销售目标是多少？"）。仅用 content embedding 会让这类 chunk 检索
    不到；纳入 heading 后相似度提升，拒答/回答话术更贴合。
    """
    if chunk.heading_path:
        return f"{chunk.heading_path}\n{chunk.content}"
    return chunk.content


def chunk_blocks(blocks: list[ParsedBlock], chunk_size: int, overlap: int) -> list[_ChunkData]:
    """将解析块按 chunk_size/overlap 切分（保留定位信息）。"""
    chunks: list[_ChunkData] = []
    idx = 0
    for block in blocks:
        text = block.text
        if not text:
            continue
        if len(text) <= chunk_size:
            chunks.append(
                _ChunkData(text, block.heading_path, block.page_number, block.paragraph_index, idx)
            )
            idx += 1
            continue
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            piece = text[start:end].strip()
            if piece:
                chunks.append(
                    _ChunkData(
                        piece, block.heading_path, block.page_number, block.paragraph_index, idx
                    )
                )
                idx += 1
            if end >= len(text):
                break
            start = end - overlap
    return chunks


async def index_document(document_id: uuid.UUID) -> None:
    """完整索引流程（在后台任务中执行）：解析→分块→embedding→入库。"""
    index_logger = logger.bind(
        module="indexing", event="index_document", document_id=str(document_id)
    )
    async with AsyncSessionLocal() as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            index_logger.warning("索引任务未找到文档")
            return
        try:
            index_logger.info("文档索引开始")
            doc.status = "indexing"
            doc.error_message = None
            await session.commit()

            file_path = Path(doc.storage_path)
            parser = get_parser(file_path)
            blocks = await parser.parse(file_path)
            chunks = chunk_blocks(blocks, settings.RAG_CHUNK_SIZE, settings.RAG_CHUNK_OVERLAP)

            embeddings = await embedding_service.embed_texts([_embed_text(c) for c in chunks])

            for chunk, emb in zip(chunks, embeddings, strict=True):
                session.add(
                    DocumentChunk(
                        id=uuid.uuid4(),
                        document_id=doc.id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        heading_path=chunk.heading_path,
                        page_number=chunk.page_number,
                        paragraph_index=chunk.paragraph_index,
                        embedding=emb,
                    )
                )
            doc.status = "indexed"
            await session.commit()
            index_logger.info("文档索引完成 chunks={}", len(chunks))
        except Exception as exc:
            doc.status = "failed"
            doc.error_message = str(exc)[:500]
            await session.commit()
            index_logger.exception("文档索引失败")
