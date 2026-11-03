"""Add the shipment management record.

Revision ID: 0003_shipments
Revises: 0002_authentication
Create Date: 2026-11-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0003_shipments"
down_revision: str | None = "0002_authentication"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shipments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shipment_reference", sa.String(length=64), nullable=False),
        sa.Column("importer", sa.String(length=255), nullable=False),
        sa.Column("supplier", sa.String(length=255), nullable=False),
        sa.Column("origin_country", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'UPLOADED', 'EXTRACTING', 'IN_REVIEW', "
            "'ACTION_REQUIRED', 'READY_FOR_EXPORT', 'EXPORTED', 'PROCESSING_FAILED')",
            name="ck_shipments_status",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shipment_reference"),
    )
    op.create_index(
        "ix_shipments_status_updated_at", "shipments", ["status", "updated_at"]
    )
    op.create_index(
        "ix_shipments_created_by_id_updated_at",
        "shipments",
        ["created_by_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_shipments_created_by_id_updated_at", table_name="shipments")
    op.drop_index("ix_shipments_status_updated_at", table_name="shipments")
    op.drop_table("shipments")
