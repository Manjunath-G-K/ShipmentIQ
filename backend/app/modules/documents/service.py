"""Document metadata transactions and shipment object-scope enforcement."""

from __future__ import annotations

from typing import BinaryIO
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    DocumentNotFoundError,
    DocumentStorageUnavailableError,
    InvalidDocumentUploadError,
    AuthorizationError,
    ShipmentNotFoundError,
)
from app.db.models import DocumentType, Shipment, ShipmentDocument, User
from app.modules.documents.storage import (
    DocumentStorage,
    DocumentStorageError,
    InvalidStoredDocumentError,
)
from app.modules.shipments.service import is_manager


def _get_shipment_for_user(
    session: Session, user: User, shipment_id: UUID
) -> Shipment:
    statement = select(Shipment).where(Shipment.id == shipment_id)
    if not is_manager(user):
        statement = statement.where(Shipment.created_by_id == user.id)
    shipment = session.scalar(statement)
    if shipment is None:
        raise ShipmentNotFoundError()
    return shipment


def list_documents(
    session: Session, user: User, shipment_id: UUID
) -> list[ShipmentDocument]:
    _get_shipment_for_user(session, user, shipment_id)
    return session.scalars(
        select(ShipmentDocument)
        .where(ShipmentDocument.shipment_id == shipment_id)
        .order_by(ShipmentDocument.created_at.desc(), ShipmentDocument.id)
    ).all()


def _get_document_for_user(
    session: Session, user: User, shipment_id: UUID, document_id: UUID
) -> ShipmentDocument:
    _get_shipment_for_user(session, user, shipment_id)
    document = session.scalar(
        select(ShipmentDocument).where(
            ShipmentDocument.id == document_id,
            ShipmentDocument.shipment_id == shipment_id,
        )
    )
    if document is None:
        raise DocumentNotFoundError()
    return document


def upload_document(
    session: Session,
    user: User,
    shipment_id: UUID,
    document_type: DocumentType,
    source: BinaryIO,
    *,
    filename: str | None,
    declared_content_type: str | None,
    storage: DocumentStorage,
) -> ShipmentDocument:
    shipment = _get_shipment_for_user(session, user, shipment_id)
    if is_manager(user):
        # Managers can review every shipment but do not upload on behalf of an executive.
        raise AuthorizationError()

    existing = session.scalar(
        select(ShipmentDocument).where(
            ShipmentDocument.shipment_id == shipment.id,
            ShipmentDocument.document_type == document_type.value,
        )
    )
    if existing is not None:
        raise ConflictError("A document of this type already exists for the shipment")

    try:
        stored = storage.save(
            source,
            filename=filename,
            declared_content_type=declared_content_type,
        )
    except InvalidStoredDocumentError as exc:
        raise InvalidDocumentUploadError(str(exc)) from exc
    except DocumentStorageError as exc:
        raise DocumentStorageUnavailableError() from exc

    document = ShipmentDocument(
        shipment_id=shipment.id,
        uploaded_by_id=user.id,
        document_type=document_type.value,
        original_filename=stored.original_filename,
        storage_key=stored.storage_key,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
    )
    if shipment.status == "DRAFT":
        shipment.status = "UPLOADED"
    session.add(document)
    try:
        session.flush()
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        try:
            storage.delete(stored.storage_key)
        except DocumentStorageError:
            pass
        raise ConflictError("A document of this type already exists for the shipment") from exc
    except Exception:
        session.rollback()
        try:
            storage.delete(stored.storage_key)
        except DocumentStorageError:
            pass
        raise
    session.refresh(document)
    return document


def open_document(
    session: Session,
    user: User,
    shipment_id: UUID,
    document_id: UUID,
    storage: DocumentStorage,
):
    document = _get_document_for_user(session, user, shipment_id, document_id)
    try:
        file_object = storage.open(document.storage_key)
    except FileNotFoundError as exc:
        raise DocumentStorageUnavailableError() from exc
    except DocumentStorageError as exc:
        raise DocumentStorageUnavailableError() from exc
    return document, file_object
