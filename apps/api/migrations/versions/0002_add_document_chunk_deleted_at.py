"""add deleted_at to document chunks

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-18

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_document_chunks_deleted_at", "document_chunks", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_deleted_at", table_name="document_chunks")
    op.drop_column("document_chunks", "deleted_at")
