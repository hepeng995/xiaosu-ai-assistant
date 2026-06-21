#!/usr/bin/env bash
# 批量索引 data/samples/ 知识库文档（解析→分块→embedding→pgvector）
#
# 特性：
#   - 幂等：内容 hash 未变的已索引文档自动跳过，避免重复消耗 embedding
#   - 同名替换：内容有变化的旧文档自动 version+1，旧 chunk 停用（由 upload_document 处理）
#   - 多格式：.md / .txt / .pdf / .docx 全支持
#
# 用法：
#   ./scripts/seed_knowledge.sh                 # 默认连 localhost:5433（docker compose 映射）
#   DATABASE_URL=... ./scripts/seed_knowledge.sh # 自定义连接串
set -euo pipefail
cd "$(dirname "$0")/.."
cd apps/api

echo "===== 批量索引知识库文档 ====="
# 本地直连 docker compose 的 postgres（映射到宿主 5433）；可通过环境变量覆盖
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://postgres:postgres@localhost:5433/xiaosu}"

uv run python - <<'PY'
import asyncio
import hashlib
import io
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import Document
from app.services.document_service import sanitize_filename, upload_document
from app.services.indexing_service import index_document

SAMPLES = Path("../../data/samples")
EXTS = {".md", ".txt", ".pdf", ".docx"}


async def main() -> None:
    files = sorted(f for f in SAMPLES.iterdir() if f.suffix.lower() in EXTS and f.is_file())
    print(f"发现 {len(files)} 个文档，开始索引（已索引且内容未变的自动跳过）...\n")
    indexed = skipped = failed = 0
    for f in files:
        original = sanitize_filename(f.name)
        content = f.read_bytes()
        file_hash = hashlib.sha256(content).hexdigest()
        try:
            async with AsyncSessionLocal() as session:
                # 幂等检查：同名 + 同 hash + 已 indexed 的跳过
                existed = await session.execute(
                    select(Document).where(
                        Document.original_filename == original,
                        Document.file_hash == file_hash,
                        Document.status == "indexed",
                        Document.deleted_at.is_(None),
                    )
                )
                if existed.scalar_one_or_none() is not None:
                    skipped += 1
                    print(f"  SKIP  {f.name}")
                    continue
                upload = UploadFile(filename=f.name, file=io.BytesIO(content))
                doc = await upload_document(upload, session)
                await index_document(doc.id)
                indexed += 1
                print(f"  OK    {f.name}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL  {f.name}: {exc}")
    print(f"\n完成: {indexed} 索引 / {skipped} 跳过 / {failed} 失败")


if __name__ == "__main__":
    asyncio.run(main())
PY
