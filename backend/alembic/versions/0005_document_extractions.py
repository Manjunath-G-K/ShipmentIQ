"""Persist OCR and structured document extraction results."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_document_extractions"
down_revision: str | None = "0004_shipment_documents"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("ocr_provider_name", sa.String(length=64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'NEEDS_REVIEW', 'FAILED')", name="ck_document_extractions_status"),
        sa.CheckConstraint("page_count >= 0", name="ck_document_extractions_page_count"),
        sa.ForeignKeyConstraint(["document_id"], ["shipment_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_document_extractions_document"),
    )
    op.create_index("ix_document_extractions_status_updated", "document_extractions", ["status", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_document_extractions_status_updated", table_name="document_extractions")
    op.drop_table("document_extractions")
