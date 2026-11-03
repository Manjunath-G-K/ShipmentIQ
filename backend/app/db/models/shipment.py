"""Shipment persistence model and backend-controlled workflow status."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ShipmentStatus(StrEnum):
    DRAFT = "DRAFT"
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    IN_REVIEW = "IN_REVIEW"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    READY_FOR_EXPORT = "READY_FOR_EXPORT"
    EXPORTED = "EXPORTED"
    PROCESSING_FAILED = "PROCESSING_FAILED"


_STATUS_VALUES = ", ".join(f"'{status.value}'" for status in ShipmentStatus)


class Shipment(Base):
    __tablename__ = "shipments"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_STATUS_VALUES})", name="ck_shipments_status"
        ),
        Index("ix_shipments_status_updated_at", "status", "updated_at"),
        Index("ix_shipments_created_by_id_updated_at", "created_by_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    created_by_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    shipment_reference: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    importer: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier: Mapped[str] = mapped_column(String(255), nullable=False)
    origin_country: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ShipmentStatus.DRAFT.value,
        server_default=ShipmentStatus.DRAFT.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    created_by: Mapped["User"] = relationship(back_populates="shipments")
