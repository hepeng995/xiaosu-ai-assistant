#!/usr/bin/env python3
"""重新索引全部已 indexed 文档（软删旧 chunks + 重建）。

适用场景：
- 更换 embedding 模型后（向量空间不同，必须重建全部 chunks）
- chunks 数据损坏或不一致时

运行方式（在 api 容器内，复用容器环境变量与依赖）：
    docker cp scripts/reindex_all.py xiaosu-api:/app/reindex_all.py
    docker exec -w /app xiaosu-api python reindex_all.py

或本地（需 DATABASE_URL 指向目标库）：
    cd apps/api && uv run python ../../scripts/reindex_all.py

注意：会先软删所有现有 chunks（旧向量作废），再用当前 embedding 配置重建。
      消耗 embedding API 配额（按文档数 × 平均 chunk 数计）。
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.db.session import AsyncSessionLocal
from app.models import Document, DocumentChunk
from app.services.indexing_service import index_document


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document).where(Document.deleted_at.is_(None))
        )
        docs = list(result.scalars().all())
        print(f"待重索引: {len(docs)} 个文档")
        # 软删所有现有 chunks（换 embedding 模型时，旧向量与新模型不在同一向量空间）
        now = datetime.now(UTC)
        await session.execute(
            update(DocumentChunk)
            .where(DocumentChunk.deleted_at.is_(None))
            .values(deleted_at=now)
        )
        await session.commit()

    success = fail = 0
    for doc in docs:
        try:
            await index_document(doc.id)
            success += 1
            print(f"  OK   {doc.original_filename}")
        except Exception as exc:
            fail += 1
            print(f"  FAIL {doc.original_filename}: {exc}")
    print(f"=== 完成: {success} OK / {fail} FAIL ===")


if __name__ == "__main__":
    asyncio.run(main())
