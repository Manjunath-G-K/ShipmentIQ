"""Transactional extraction orchestration and access-control reuse."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ExtractionConflictError, ExtractionNotFoundError
from app.db.models import DocumentExtraction, DocumentType, ExtractionStatus, Shipment, ShipmentDocument, ShipmentStatus, User
from app.modules.documents.service import _get_shipment_for_user
from app.modules.documents.storage import DocumentStorage
from app.modules.extraction.providers import AIExtractionProvider, OCRProvider
from app.modules.extraction.schemas import ExtractionResult, normalize_json_provider_payload
from app.modules.review.service import sync_review_fields


def _get_document(session: Session, user: User, shipment_id: UUID, document_id: UUID) -> ShipmentDocument:
    _get_shipment_for_user(session, user, shipment_id)
    document = session.scalar(select(ShipmentDocument).where(ShipmentDocument.id == document_id, ShipmentDocument.shipment_id == shipment_id))
    if document is None:
        raise ExtractionNotFoundError()
    return document


def get_extraction(session: Session, user: User, shipment_id: UUID, document_id: UUID) -> DocumentExtraction:
    _get_document(session, user, shipment_id, document_id)
    extraction = session.scalar(select(DocumentExtraction).where(DocumentExtraction.document_id == document_id))
    if extraction is None:
        raise ExtractionNotFoundError()
    return extraction


def _safe_failure(exc: Exception) -> tuple[str, str]:
    from app.modules.extraction.providers import AIProviderError, OCRProviderError

    if isinstance(exc, OCRProviderError):
        return "OCR_FAILED", "Document text extraction failed"
    if isinstance(exc, ValidationError):
        return "MALFORMED_AI_RESPONSE", "Extraction provider returned invalid structured data"
    if isinstance(exc, AIProviderError):
        return "AI_PROVIDER_FAILED", "Configured extraction provider failed"
    return "PROCESSING_FAILED", "Document processing failed"


def process_extraction(
    session: Session,
    user: User,
    shipment_id: UUID,
    document_id: UUID,
    storage: DocumentStorage,
    ocr_provider: OCRProvider,
    ai_provider: AIExtractionProvider,
) -> DocumentExtraction:
    document = _get_document(session, user, shipment_id, document_id)
    extraction = session.scalar(select(DocumentExtraction).where(DocumentExtraction.document_id == document.id).with_for_update())
    if extraction is not None and extraction.status == ExtractionStatus.PROCESSING.value:
        raise ExtractionConflictError()
    if extraction is None:
        extraction = DocumentExtraction(document_id=document.id, provider_name=ai_provider.name, ocr_provider_name=ocr_provider.name)
        session.add(extraction)
    extraction.status = ExtractionStatus.PROCESSING.value
    extraction.provider_name = ai_provider.name
    extraction.ocr_provider_name = ocr_provider.name
    extraction.error_code = None
    extraction.error_message = None
    extraction.started_at = datetime.now(timezone.utc)
    shipment = session.get(Shipment, shipment_id, with_for_update=True)
    if shipment is not None:
        shipment.status = ShipmentStatus.EXTRACTING.value
    session.commit()

    try:
        with storage.open(document.storage_key) as source:
            pages = ocr_provider.extract(source.read(), document.content_type)
        extraction.page_count = len(pages)
        readable_pages = [page for page in pages if page.readable and page.text.strip()]
        if not readable_pages:
            result = ExtractionResult(document_type=document.document_type, pages=pages)
            extraction.status = ExtractionStatus.NEEDS_REVIEW.value
            extraction.error_code = "UNREADABLE_DOCUMENT"
            extraction.error_message = "No readable page text was available; manual entry is required"
        else:
            raw_result = ai_provider.extract(pages, document.document_type)
            result = ExtractionResult.model_validate(
                normalize_json_provider_payload(raw_result), strict=True
            )
            result.document_type = DocumentType(document.document_type)
            result.pages = pages
            extraction.status = ExtractionStatus.NEEDS_REVIEW.value if result.has_missing_values() or any(not page.readable for page in pages) else ExtractionStatus.SUCCEEDED.value
        extraction.result = result.model_dump(mode="json")
        extraction.page_count = len(pages)
        extraction.completed_at = datetime.now(timezone.utc)
        sync_review_fields(session, document, result, user.id)
        shipment = session.get(Shipment, shipment_id, with_for_update=True)
        if shipment is not None and shipment.status != ShipmentStatus.ACTION_REQUIRED.value:
            shipment.status = ShipmentStatus.IN_REVIEW.value
        session.commit()
    except Exception as exc:
        session.rollback()
        code, message = _safe_failure(exc)
        extraction = session.scalar(select(DocumentExtraction).where(DocumentExtraction.document_id == document.id).with_for_update())
        if extraction is None:
            extraction = DocumentExtraction(document_id=document.id, provider_name=ai_provider.name, ocr_provider_name=ocr_provider.name)
            session.add(extraction)
        extraction.status = ExtractionStatus.FAILED.value
        extraction.error_code = code
        extraction.error_message = message
        extraction.completed_at = datetime.now(timezone.utc)
        shipment = session.get(Shipment, shipment_id, with_for_update=True)
        if shipment is not None:
            shipment.status = ShipmentStatus.PROCESSING_FAILED.value
        session.commit()
    session.refresh(extraction)
    return extraction
