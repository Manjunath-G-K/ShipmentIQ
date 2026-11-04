"""Private shipment-document metadata persistence model."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentType(StrEnum):
    INVOICE = "INVOICE"
    PACKING_LIST = "PACKING_LIST"
    BILL_OF_LADING = "BILL_OF_LADING"


_DOCUMENT_TYPE_VALUES = ", ".join(f"'{document_type.value}'" for document_type in DocumentType)


class ShipmentDocument(Base):
    __tablename__ = "shipment_documents"
    __table_args__ = (
        CheckConstraint(
            f"document_type IN ({_DOCUMENT_TYPE_VALUES})",
            name="ck_shipment_documents_type",
        ),
        CheckConstraint("size_bytes > 0", name="ck_shipment_documents_size"),
        UniqueConstraint(
            "shipment_id", "document_type", name="uq_shipment_documents_type"
        ),
        Index("ix_shipment_documents_shipment_created", "shipment_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    shipment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shipments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    uploaded_by_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    shipment: Mapped["Shipment"] = relationship(back_populates="documents")
    uploaded_by: Mapped["User"] = relationship(back_populates="uploaded_documents")
