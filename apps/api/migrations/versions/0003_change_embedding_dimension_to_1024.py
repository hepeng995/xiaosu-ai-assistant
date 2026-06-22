"""change embedding dimension from 1536 to 1024

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-22

切换 embedding 模型 Qwen/Qwen3-VL-Embedding-8B（多模态，1536 维，中文语义弱）
→ BAAI/bge-m3（纯文本，1024 维，中文语义强）。

根因：旧模型对中文 RAG 检索区分度不足——正确 chunk 的 raw score 仅 0.5776
（< RAG_SCORE_THRESHOLD=0.72），而无关 chunk 反而更高（0.6443），导致拒答。
bge-m3 实测正确 chunk score 0.7413，能稳定命中。

向量维度不兼容（1536 ≠ 1024），无法直接 cast，必须 USING NULL 清空旧向量。
迁移后**必须运行 scripts/reindex_all.py 全量重索引**才能恢复检索能力。
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # VECTOR(1536) → VECTOR(1024)：维度不兼容，清空旧向量（重索引时用新模型重建）
    op.execute(
        "ALTER TABLE document_chunks ALTER COLUMN embedding TYPE VECTOR(1024) USING NULL"
    )


def downgrade() -> None:
    # 回到 1536 维（同样清空，需用 1536 维模型重索引）
    op.execute(
        "ALTER TABLE document_chunks ALTER COLUMN embedding TYPE VECTOR(1536) USING NULL"
    )
