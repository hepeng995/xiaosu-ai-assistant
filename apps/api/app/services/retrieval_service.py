"""知识库检索服务。

真实模式：pgvector 余弦相似度 + 阈值过滤 + 软删除过滤。
mock 模式（未配置 EMBEDDING_API_KEY）：字符重叠近似检索，便于无 key 环境验证命中流程。
"""

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.observability import trace_span
from app.llm.embedding import embedding_service

# 真实模式：余弦相似度检索
_VECTOR_SQL = text(
    """
    SELECT c.id, c.document_id, c.content, c.heading_path, c.page_number,
           c.paragraph_index, d.original_filename AS filename,
           1 - (c.embedding <=> CAST(:emb AS vector)) AS score
    FROM document_chunks c
    JOIN documents d ON c.document_id = d.id
    WHERE d.deleted_at IS NULL AND d.status = 'indexed' AND c.deleted_at IS NULL
    ORDER BY c.embedding <=> CAST(:emb AS vector)
    LIMIT :top_k
    """
)

# mock 模式：拉取全部有效分块做字符重叠打分
_LIST_SQL = text(
    """
    SELECT c.id, c.document_id, c.content, c.heading_path, c.page_number,
           c.paragraph_index, d.original_filename AS filename
    FROM document_chunks c
    JOIN documents d ON c.document_id = d.id
    WHERE d.deleted_at IS NULL AND d.status = 'indexed' AND c.deleted_at IS NULL
    """
)

# mock 字符重叠阈值（仅用于无 key 环境的流程验证；真实模式走 RAG_SCORE_THRESHOLD）
_MOCK_THRESHOLD = 0.5


def _row_to_item(row: Mapping, score: float) -> dict:
    return {
        "chunk_id": str(row["id"]),
        "document_id": str(row["document_id"]),
        "filename": row["filename"],
        "content": row["content"],
        "heading_path": row["heading_path"],
        "page_number": row["page_number"],
        "paragraph_index": row["paragraph_index"],
        "quote": (row["content"] or "")[:120],
        "score": score,
    }


async def search_knowledge(
    query: str, session: AsyncSession, top_k: int | None = None
) -> list[dict]:
    """检索知识库：真实走 pgvector，mock 走字符重叠。"""
    top_k = top_k or settings.RAG_TOP_K
    with trace_span(
        "retrieval_search",
        metadata={"top_k": top_k, "mode": "mock" if embedding_service.use_mock else "vector"},
    ) as span:
        if embedding_service.use_mock:
            items = await _mock_search(query, session, top_k)
        else:
            items = await _vector_search(query, session, top_k)
        span["metadata"] = {
            "top_k": top_k,
            "result_count": len(items),
            "mode": "mock" if embedding_service.use_mock else "vector",
        }
        return items


async def _vector_search(query: str, session: AsyncSession, top_k: int) -> list[dict]:
    query_emb = await embedding_service.embed_query(query)
    emb_str = "[" + ",".join(f"{x:.7f}" for x in query_emb) + "]"
    result = await session.execute(_VECTOR_SQL, {"emb": emb_str, "top_k": top_k})
    items: list[dict] = []
    for row in result.mappings():
        score = float(row["score"])
        if score >= settings.RAG_SCORE_THRESHOLD:
            items.append(_row_to_item(row, score))
    return items


async def _mock_search(query: str, session: AsyncSession, top_k: int) -> list[dict]:
    """字符重叠近似检索（无 API key 时验证命中流程，非真实语义）。"""
    result = await session.execute(_LIST_SQL)
    qset = set(query)
    scored: list[tuple[float, Mapping]] = []
    for row in result.mappings():
        content = row["content"] or ""
        overlap = len(qset & set(content))
        if overlap == 0:
            continue
        score = overlap / max(len(qset), 1)
        if score >= _MOCK_THRESHOLD:
            scored.append((score, row))
    scored.sort(key=lambda x: -x[0])
    return [_row_to_item(row, score) for score, row in scored[:top_k]]
