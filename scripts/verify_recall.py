"""诊断：重索引后"销售目标"query 与 FAQ chunk 的 raw 相似度（绕过阈值看真相）。"""

import asyncio
from datetime import datetime

from sqlalchemy import text
from app.db.session import AsyncSessionLocal
from app.llm.embedding import embedding_service


async def main() -> None:
    query = "2030 年的销售目标是多少？"
    async with AsyncSessionLocal() as session:
        emb = await embedding_service.embed_query(query)
        emb_str = "[" + ",".join(f"{x:.7f}" for x in emb) + "]"
        sql = text(
            """
            SELECT d.original_filename, c.heading_path, left(c.content, 45) AS preview,
                   1 - (c.embedding <=> CAST(:emb AS vector)) AS score
            FROM document_chunks c JOIN documents d ON c.document_id = d.id
            WHERE c.deleted_at IS NULL AND d.status = 'indexed'
            ORDER BY c.embedding <=> CAST(:emb AS vector)
            LIMIT 8
            """
        )
        result = await session.execute(sql, {"emb": emb_str})
        print(f"=== query: {query} (raw top 8, 不过阈值) ===")
        for row in result:
            mark = " ★FAQ" if "销售目标" in (row.heading_path or "") else ""
            print(f"  score={row.score:.4f}  {row.original_filename}  | {(row.heading_path or '')[:38]}{mark}")
            print(f"    {row.preview}")


if __name__ == "__main__":
    print(f"诊断时间: {datetime.now()}")
    asyncio.run(main())
