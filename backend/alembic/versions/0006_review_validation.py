"""Add human review, field revisions, and validation results."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0006_review_validation"
down_revision: str | None = "0005_document_extractions"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_path", sa.String(length=160), nullable=False),
        sa.Column("value_type", sa.String(length=16), nullable=False),
        sa.Column("extracted_value", postgresql.JSONB(), nullable=True),
        sa.Column("current_value", postgresql.JSONB(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("source_references", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="NEEDS_REVIEW"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('NEEDS_REVIEW', 'CONFIRMED', 'CORRECTED', 'REJECTED')", name="ck_review_fields_status"),
        sa.CheckConstraint("version > 0", name="ck_review_fields_version"),
        sa.ForeignKeyConstraint(["document_id"], ["shipment_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_reviewed_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "field_path", name="uq_review_fields_document_path"),
    )
    op.create_index("ix_review_fields_document_status", "review_fields", ["document_id", "status"])

    op.create_table(
        "field_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("previous_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("action IN ('EXTRACTED', 'CORRECTED', 'CONFIRMED', 'REJECTED')", name="ck_field_revisions_action"),
        sa.ForeignKeyConstraint(["field_id"], ["review_fields.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_field_revisions_field_created", "field_revisions", ["field_id", "created_at"])

    op.create_table(
        "shipment_validations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("evaluated_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('PASSED', 'FAILED', 'UNRESOLVED', 'STALE')", name="ck_shipment_validations_status"),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evaluated_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shipment_id", "rule_key", name="uq_shipment_validations_rule"),
    )
    op.create_index("ix_shipment_validations_shipment_status", "shipment_validations", ["shipment_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_shipment_validations_shipment_status", table_name="shipment_validations")
    op.drop_table("shipment_validations")
    op.drop_index("ix_field_revisions_field_created", table_name="field_revisions")
    op.drop_table("field_revisions")
    op.drop_index("ix_review_fields_document_status", table_name="review_fields")
    op.drop_table("review_fields")
