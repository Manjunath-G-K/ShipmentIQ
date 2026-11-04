"""Add private shipment document metadata.

Revision ID: 0004_shipment_documents
Revises: 0003_shipments
Create Date: 2026-11-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0004_shipment_documents"
down_revision: str | None = "0003_shipments"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shipment_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=128), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "document_type IN ('INVOICE', 'PACKING_LIST', 'BILL_OF_LADING')",
            name="ck_shipment_documents_type",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_shipment_documents_size"),
        sa.ForeignKeyConstraint(
            ["shipment_id"], ["shipments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
        sa.UniqueConstraint(
            "shipment_id", "document_type", name="uq_shipment_documents_type"
        ),
    )
    op.create_index(
        "ix_shipment_documents_shipment_created",
        "shipment_documents",
        ["shipment_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shipment_documents_shipment_created", table_name="shipment_documents"
    )
    op.drop_table("shipment_documents")
