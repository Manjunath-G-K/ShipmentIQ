"""Human-review, field-revision, and deterministic-validation persistence models."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReviewFieldStatus(StrEnum):
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    REJECTED = "REJECTED"


class ReviewAction(StrEnum):
    EXTRACTED = "EXTRACTED"
    CORRECTED = "CORRECTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class ValidationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    UNRESOLVED = "UNRESOLVED"
    STALE = "STALE"


_REVIEW_STATUS_VALUES = ", ".join(f"'{item.value}'" for item in ReviewFieldStatus)
_REVIEW_ACTION_VALUES = ", ".join(f"'{item.value}'" for item in ReviewAction)
_VALIDATION_STATUS_VALUES = ", ".join(f"'{item.value}'" for item in ValidationStatus)


class ReviewField(Base):
    """Current human-review state for one extracted field path."""

    __tablename__ = "review_fields"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_REVIEW_STATUS_VALUES})", name="ck_review_fields_status"
        ),
        CheckConstraint("version > 0", name="ck_review_fields_version"),
        UniqueConstraint("document_id", "field_path", name="uq_review_fields_document_path"),
        Index("ix_review_fields_document_status", "document_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shipment_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_path: Mapped[str] = mapped_column(String(160), nullable=False)
    value_type: Mapped[str] = mapped_column(String(16), nullable=False)
    extracted_value: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    current_value: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    source_references: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ReviewFieldStatus.NEEDS_REVIEW.value
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_reviewed_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    document: Mapped["ShipmentDocument"] = relationship()
    revisions: Mapped[list["FieldRevision"]] = relationship(
        back_populates="field", cascade="all, delete-orphan", lazy="noload"
    )


class FieldRevision(Base):
    """Append-only audit record for an extracted-field action."""

    __tablename__ = "field_revisions"
    __table_args__ = (
        CheckConstraint(
            f"action IN ({_REVIEW_ACTION_VALUES})", name="ck_field_revisions_action"
        ),
        Index("ix_field_revisions_field_created", "field_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    field_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("review_fields.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_value: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[object | None] = mapped_column(JSONB, nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    field: Mapped[ReviewField] = relationship(back_populates="revisions")


class ShipmentValidation(Base):
    """Latest deterministic validation result for one shipment rule."""

    __tablename__ = "shipment_validations"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_VALIDATION_STATUS_VALUES})", name="ck_shipment_validations_status"
        ),
        UniqueConstraint("shipment_id", "rule_key", name="uq_shipment_validations_rule"),
        Index("ix_shipment_validations_shipment_status", "shipment_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    shipment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("shipments.id", ondelete="RESTRICT"), nullable=False
    )
    rule_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    evaluated_by_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
