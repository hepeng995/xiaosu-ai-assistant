#!/usr/bin/env python3
"""验证「删除文档后不再命中 + 恢复后重新命中」的回归脚本（运维用，不入库）。"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.services import document_service
from app.services.retrieval_service import search_knowledge

DOC_NAME = "办公用品领用与耗材管理办法.md"
QUERY = "打印纸每个月能领多少？"


async def main() -> None:
    async with AsyncSessionLocal() as s:
        row = (
            await s.execute(
                text(
                    "SELECT id, status FROM documents WHERE original_filename=:n "
                    "AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 1"
                ),
                {"n": DOC_NAME},
            )
        ).first()
        if row is None:
            print(f"FAIL: 文档 {DOC_NAME} 不存在")
            return
        doc_id = row[0]
        print(f"doc_id={doc_id} status={row[1]}")

        before = await search_knowledge(QUERY, s)
        print(f"删除前 hits={len(before)} (top score={before[0]['score']:.4f})" if before else "删除前 hits=0")

        ok = await document_service.soft_delete_document(doc_id, s)
        print(f"soft_delete ok={ok}")

        after = await search_knowledge(QUERY, s)
        print(f"删除后 hits={len(after)}")

        # 恢复
        await s.execute(
            text("UPDATE documents SET deleted_at=NULL, status='indexed' WHERE id=:id"),
            {"id": doc_id},
        )
        await s.execute(
            text("UPDATE document_chunks SET deleted_at=NULL WHERE document_id=:id"),
            {"id": doc_id},
        )
        await s.commit()

        restored = await search_knowledge(QUERY, s)
        print(
            f"恢复后 hits={len(restored)} (top score={restored[0]['score']:.4f})"
            if restored
            else "恢复后 hits=0"
        )

        # 断言
        assert len(before) > 0, "删除前应命中"
        assert len(after) == 0, "删除后不应命中"
        assert len(restored) > 0, "恢复后应重新命中"
        print("=== 断言全部通过 ✅ ===")


if __name__ == "__main__":
    asyncio.run(main())
