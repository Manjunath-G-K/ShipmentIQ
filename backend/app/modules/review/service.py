"""Human review transactions and deterministic cross-document validation."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    InvalidFieldValueError,
    ReviewFieldNotFoundError,
    ShipmentNotFoundError,
)
from app.db.models import (
    DocumentExtraction,
    DocumentType,
    FieldRevision,
    ReviewAction,
    ReviewField,
    ReviewFieldStatus,
    Shipment,
    ShipmentDocument,
    ShipmentValidation,
    User,
    ValidationStatus,
)
from app.modules.documents.service import _get_document_for_user, _get_shipment_for_user
from app.modules.extraction.schemas import ExtractionResult
from app.modules.review.field_map import FieldSnapshot, flatten_extraction


VALIDATION_RULES = (
    "invoice_total_vs_line_items",
    "package_count_across_documents",
    "gross_weight_across_documents",
    "net_weight_across_documents",
)
_LINE_ITEM_PATH = re.compile(r"^line_items\[(\d+)\]\.(quantity|unit_price)$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _field_value(field: ReviewField | None) -> Any:
    return None if field is None else field.current_value


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _normalized_equal(values: list[Any], value_type: str) -> bool:
    if value_type in {"decimal", "integer"}:
        converted = [_decimal(value) for value in values]
        return all(value is not None for value in converted) and len(set(converted)) == 1
    return len(set(str(value).strip() for value in values)) == 1


def _field_flags(
    field: ReviewField,
    extraction: DocumentExtraction | None,
    low_confidence_threshold: float,
) -> list[str]:
    flags: list[str] = []
    if field.current_value is None:
        flags.append("MISSING")
    if field.status == ReviewFieldStatus.REJECTED.value:
        flags.append("REJECTED")
    if field.status in {
        ReviewFieldStatus.NEEDS_REVIEW.value,
        ReviewFieldStatus.CORRECTED.value,
    }:
        flags.append("NEEDS_CONFIRMATION")
    if field.confidence is None or float(field.confidence) < low_confidence_threshold:
        flags.append("LOW_CONFIDENCE")
    if extraction and extraction.result:
        pages = extraction.result.get("pages", [])
        if any(not page.get("readable", False) for page in pages) and field.current_value is None:
            flags.append("UNREADABLE_PAGE")
    return flags


def _get_field_for_user(session: Session, user: User, field_id: UUID) -> ReviewField:
    row = session.execute(
        select(ReviewField, ShipmentDocument.shipment_id)
        .join(ShipmentDocument, ShipmentDocument.id == ReviewField.document_id)
        .where(ReviewField.id == field_id)
    ).first()
    if row is None:
        raise ReviewFieldNotFoundError()
    _get_shipment_for_user(session, user, row[1])
    return row[0]


def _append_revision(
    session: Session,
    field: ReviewField,
    actor_id: UUID,
    action: ReviewAction,
    previous_value: Any,
    new_value: Any,
    note: str | None,
) -> None:
    session.add(
        FieldRevision(
            field_id=field.id,
            actor_id=actor_id,
            action=action.value,
            previous_value=previous_value,
            new_value=new_value,
            note=note,
        )
    )


def sync_review_fields(
    session: Session,
    document: ShipmentDocument,
    result: ExtractionResult,
    actor_id: UUID,
) -> None:
    """Materialize extraction fields without overwriting human-reviewed values."""

    snapshots = flatten_extraction(result)
    changed_field_id: UUID | None = None
    for snapshot in snapshots:
        field = session.scalar(
            select(ReviewField)
            .where(
                ReviewField.document_id == document.id,
                ReviewField.field_path == snapshot.path,
            )
            .with_for_update()
        )
        if field is None:
            field = ReviewField(
                document_id=document.id,
                field_path=snapshot.path,
                value_type=snapshot.value_type,
                extracted_value=snapshot.value,
                current_value=snapshot.value,
                confidence=snapshot.confidence,
                source_references=snapshot.sources,
                status=ReviewFieldStatus.NEEDS_REVIEW.value,
                version=1,
            )
            session.add(field)
            session.flush()
            _append_revision(
                session, field, actor_id, ReviewAction.EXTRACTED, None, snapshot.value, None
            )
            if changed_field_id is None:
                changed_field_id = field.id
            continue

        previous_extracted = field.extracted_value
        field.extracted_value = snapshot.value
        field.confidence = snapshot.confidence
        field.source_references = snapshot.sources
        if (
            field.status == ReviewFieldStatus.NEEDS_REVIEW.value
            and field.current_value == previous_extracted
        ):
            if field.current_value != snapshot.value:
                field.current_value = snapshot.value
                if changed_field_id is None:
                    changed_field_id = field.id
        _append_revision(
            session,
            field,
            actor_id,
            ReviewAction.EXTRACTED,
            previous_extracted,
            snapshot.value,
            "Extraction rerun; human-reviewed current value was preserved",
        )
    if changed_field_id is not None:
        _invalidate_validations(session, document.shipment_id, changed_field_id)


def _invalidate_validations(session: Session, shipment_id: UUID, field_id: UUID) -> None:
    validations = session.scalars(
        select(ShipmentValidation)
        .where(ShipmentValidation.shipment_id == shipment_id)
        .with_for_update()
    ).all()
    if not validations:
        return
    for validation in validations:
        validation.status = ValidationStatus.STALE.value
        validation.details = {
            "reason": "field_changed",
            "field_id": str(field_id),
            "message": "Validation must be rerun after a field correction or rejection",
        }
    shipment = session.get(Shipment, shipment_id, with_for_update=True)
    if shipment is not None:
        shipment.status = "ACTION_REQUIRED"


def _validate_value(field: ReviewField, value: Any) -> Any:
    if value is None:
        raise InvalidFieldValueError("Use reject for an explicitly rejected field")
    if isinstance(value, (dict, list, bool)):
        raise InvalidFieldValueError("Field corrections must be scalar values")
    if field.value_type == "string":
        if not isinstance(value, str) or not value.strip() or len(value) > 1000:
            raise InvalidFieldValueError("Expected a non-empty string value")
        return value.strip()
    if field.value_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise InvalidFieldValueError("Expected a non-negative integer value")
        return value
    if field.value_type == "decimal":
        decimal = _decimal(value)
        if decimal is None or decimal < 0:
            raise InvalidFieldValueError("Expected a non-negative numeric value")
        return str(decimal)
    if field.value_type == "date":
        if not isinstance(value, str):
            raise InvalidFieldValueError("Expected an ISO date string")
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise InvalidFieldValueError("Expected an ISO date string") from exc
        return value
    raise InvalidFieldValueError("Unsupported field type")


def correct_field(
    session: Session,
    user: User,
    field_id: UUID,
    value: Any,
    note: str | None,
    expected_version: int,
) -> ReviewField:
    field = _get_field_for_user(session, user, field_id)
    field = session.scalar(select(ReviewField).where(ReviewField.id == field.id).with_for_update())
    if field is None:
        raise ReviewFieldNotFoundError()
    if field.version != expected_version:
        raise ConflictError("Field has changed; reload before correcting it")
    normalized = _validate_value(field, value)
    previous = field.current_value
    field.current_value = normalized
    field.status = ReviewFieldStatus.CORRECTED.value
    field.version += 1
    field.last_reviewed_by_id = user.id
    field.last_reviewed_at = _now()
    _append_revision(session, field, user.id, ReviewAction.CORRECTED, previous, normalized, note)
    shipment_id = session.scalar(select(ShipmentDocument.shipment_id).where(ShipmentDocument.id == field.document_id))
    if shipment_id:
        _invalidate_validations(session, shipment_id, field.id)
    session.commit()
    session.refresh(field)
    return field


def confirm_field(
    session: Session,
    user: User,
    field_id: UUID,
    note: str | None,
    expected_version: int,
) -> ReviewField:
    field = _get_field_for_user(session, user, field_id)
    field = session.scalar(select(ReviewField).where(ReviewField.id == field.id).with_for_update())
    if field is None:
        raise ReviewFieldNotFoundError()
    if field.version != expected_version:
        raise ConflictError("Field has changed; reload before confirming it")
    if field.current_value is None:
        raise InvalidFieldValueError("A missing or rejected field cannot be confirmed")
    previous_status = field.status
    field.status = ReviewFieldStatus.CONFIRMED.value
    field.version += 1
    field.last_reviewed_by_id = user.id
    field.last_reviewed_at = _now()
    _append_revision(session, field, user.id, ReviewAction.CONFIRMED, field.current_value, field.current_value, note or previous_status)
    session.commit()
    session.refresh(field)
    return field


def reject_field(
    session: Session,
    user: User,
    field_id: UUID,
    note: str | None,
    expected_version: int,
) -> ReviewField:
    field = _get_field_for_user(session, user, field_id)
    field = session.scalar(select(ReviewField).where(ReviewField.id == field.id).with_for_update())
    if field is None:
        raise ReviewFieldNotFoundError()
    if field.version != expected_version:
        raise ConflictError("Field has changed; reload before rejecting it")
    previous = field.current_value
    field.current_value = None
    field.status = ReviewFieldStatus.REJECTED.value
    field.version += 1
    field.last_reviewed_by_id = user.id
    field.last_reviewed_at = _now()
    _append_revision(session, field, user.id, ReviewAction.REJECTED, previous, None, note)
    shipment_id = session.scalar(select(ShipmentDocument.shipment_id).where(ShipmentDocument.id == field.document_id))
    if shipment_id:
        _invalidate_validations(session, shipment_id, field.id)
    session.commit()
    session.refresh(field)
    return field


def get_revisions(session: Session, user: User, field_id: UUID) -> list[FieldRevision]:
    field = _get_field_for_user(session, user, field_id)
    return session.scalars(
        select(FieldRevision)
        .where(FieldRevision.field_id == field.id)
        .order_by(FieldRevision.created_at, FieldRevision.id)
    ).all()


def _validation_details(
    path: str,
    documents: list[ShipmentDocument],
    fields_by_document: dict[UUID, dict[str, ReviewField]],
) -> tuple[ValidationStatus, dict]:
    observations = []
    for document in documents:
        field = fields_by_document.get(document.id, {}).get(path)
        if field is not None and field.current_value is not None:
            observations.append(
                {
                    "document_id": str(document.id),
                    "document_type": document.document_type,
                    "field_path": path,
                    "value": field.current_value,
                    "review_status": field.status,
                }
            )
    details = {"field_path": path, "observations": observations}
    if len(observations) < 2:
        details["comparison"] = "unavailable"
        return ValidationStatus.UNRESOLVED, details
    value_type = "decimal" if "weight" in path else "integer"
    details["comparison"] = "equal" if _normalized_equal([item["value"] for item in observations], value_type) else "different"
    return (
        ValidationStatus.PASSED if details["comparison"] == "equal" else ValidationStatus.FAILED,
        details,
    )


def _invoice_total_validation(
    documents: list[ShipmentDocument],
    fields_by_document: dict[UUID, dict[str, ReviewField]],
) -> tuple[ValidationStatus, dict]:
    invoice = next((document for document in documents if document.document_type == DocumentType.INVOICE.value), None)
    if invoice is None:
        return ValidationStatus.UNRESOLVED, {"comparison": "unavailable", "reason": "invoice_document_missing"}
    fields = fields_by_document.get(invoice.id, {})
    total = fields.get("invoice.total")
    quantities: dict[int, Any] = {}
    unit_prices: dict[int, Any] = {}
    for path, field in fields.items():
        match = _LINE_ITEM_PATH.match(path)
        if not match:
            continue
        (quantities if match.group(2) == "quantity" else unit_prices)[int(match.group(1))] = field.current_value
    if total is None or total.current_value is None or not quantities or set(quantities) != set(unit_prices):
        return ValidationStatus.UNRESOLVED, {"comparison": "unavailable", "reason": "invoice_total_or_line_items_missing"}
    line_total = Decimal("0")
    items = []
    for index in sorted(quantities):
        quantity = _decimal(quantities[index])
        unit_price = _decimal(unit_prices[index])
        if quantity is None or unit_price is None:
            return ValidationStatus.UNRESOLVED, {"comparison": "unavailable", "reason": "line_item_value_missing", "line_index": index}
        amount = quantity * unit_price
        line_total += amount
        items.append({"line_index": index, "quantity": str(quantity), "unit_price": str(unit_price), "amount": str(amount)})
    invoice_total = _decimal(total.current_value)
    if invoice_total is None:
        return ValidationStatus.UNRESOLVED, {"comparison": "unavailable", "reason": "invoice_total_invalid"}
    return (
        ValidationStatus.PASSED if invoice_total == line_total else ValidationStatus.FAILED,
        {"comparison": "equal" if invoice_total == line_total else "different", "invoice_total": str(invoice_total), "line_item_total": str(line_total), "line_items": items},
    )


def _upsert_validation(
    session: Session,
    shipment_id: UUID,
    rule_key: str,
    status: ValidationStatus,
    details: dict,
    actor_id: UUID,
) -> ShipmentValidation:
    validation = session.scalar(
        select(ShipmentValidation)
        .where(ShipmentValidation.shipment_id == shipment_id, ShipmentValidation.rule_key == rule_key)
        .with_for_update()
    )
    if validation is None:
        validation = ShipmentValidation(shipment_id=shipment_id, rule_key=rule_key)
        session.add(validation)
    validation.status = status.value
    validation.details = details
    validation.evaluated_by_id = actor_id
    validation.evaluated_at = _now()
    return validation


def run_validations(session: Session, user: User, shipment_id: UUID) -> list[ShipmentValidation]:
    shipment = _get_shipment_for_user(session, user, shipment_id)
    shipment = session.scalar(select(Shipment).where(Shipment.id == shipment.id).with_for_update())
    if shipment is None:
        raise ShipmentNotFoundError()
    documents = session.scalars(
        select(ShipmentDocument).where(ShipmentDocument.shipment_id == shipment.id).order_by(ShipmentDocument.document_type, ShipmentDocument.id)
    ).all()
    field_rows = session.scalars(
        select(ReviewField).join(ShipmentDocument, ShipmentDocument.id == ReviewField.document_id).where(ShipmentDocument.shipment_id == shipment.id)
    ).all()
    fields_by_document: dict[UUID, dict[str, ReviewField]] = defaultdict(dict)
    for field in field_rows:
        fields_by_document[field.document_id][field.field_path] = field
    checks = {
        "invoice_total_vs_line_items": _invoice_total_validation(documents, fields_by_document),
        "package_count_across_documents": _validation_details("shipment.packages", documents, fields_by_document),
        "gross_weight_across_documents": _validation_details("shipment.gross_weight_kg", documents, fields_by_document),
        "net_weight_across_documents": _validation_details("shipment.net_weight_kg", documents, fields_by_document),
    }
    results = [
        _upsert_validation(session, shipment.id, rule, status, details, user.id)
        for rule, (status, details) in checks.items()
    ]
    if any(result.status in {ValidationStatus.FAILED.value, ValidationStatus.UNRESOLVED.value} for result in results):
        shipment.status = "ACTION_REQUIRED"
    else:
        shipment.status = "IN_REVIEW"
    session.commit()
    for result in results:
        session.refresh(result)
    return results


def get_validations(session: Session, user: User, shipment_id: UUID) -> list[ShipmentValidation]:
    _get_shipment_for_user(session, user, shipment_id)
    return session.scalars(
        select(ShipmentValidation).where(ShipmentValidation.shipment_id == shipment_id).order_by(ShipmentValidation.rule_key)
    ).all()


def review_snapshot(
    session: Session,
    user: User,
    shipment_id: UUID,
    low_confidence_threshold: float,
) -> dict:
    _get_shipment_for_user(session, user, shipment_id)
    documents = session.scalars(
        select(ShipmentDocument)
        .where(ShipmentDocument.shipment_id == shipment_id)
        .order_by(ShipmentDocument.document_type, ShipmentDocument.id)
    ).all()
    document_ids = [document.id for document in documents]
    fields = session.scalars(
        select(ReviewField).where(ReviewField.document_id.in_(document_ids))
    ).all() if document_ids else []
    fields_by_document: dict[UUID, list[ReviewField]] = defaultdict(list)
    for field in fields:
        fields_by_document[field.document_id].append(field)
    extractions = session.scalars(
        select(DocumentExtraction).where(DocumentExtraction.document_id.in_(document_ids))
    ).all() if document_ids else []
    extractions_by_document = {extraction.document_id: extraction for extraction in extractions}
    document_payloads = []
    for document in documents:
        extraction = extractions_by_document.get(document.id)
        document_payloads.append(
            {
                "id": document.id,
                "document_type": document.document_type,
                "extraction_status": extraction.status if extraction else None,
                "extraction_error_code": extraction.error_code if extraction else None,
                "page_count": extraction.page_count if extraction else 0,
                "fields": [
                    {
                        "id": field.id,
                        "document_id": field.document_id,
                        "field_path": field.field_path,
                        "value_type": field.value_type,
                        "value": field.current_value,
                        "extracted_value": field.extracted_value,
                        "confidence": float(field.confidence) if field.confidence is not None else None,
                        "source_references": field.source_references,
                        "status": field.status,
                        "version": field.version,
                        "flags": _field_flags(field, extraction, low_confidence_threshold),
                        "last_reviewed_by_id": field.last_reviewed_by_id,
                        "last_reviewed_at": field.last_reviewed_at,
                    }
                    for field in sorted(fields_by_document.get(document.id, []), key=lambda item: item.field_path)
                ],
            }
        )
    return {
        "shipment_id": shipment_id,
        "documents": document_payloads,
        "validations": get_validations(session, user, shipment_id),
    }


def _metric(key: str, counts: dict[str, int]) -> dict:
    denominator = counts["confirmed_count"] + counts["corrected_count"] + counts["rejected_count"]
    return {
        "key": key,
        **counts,
        "reviewed_count": denominator,
        "accuracy_percent": round(counts["confirmed_count"] * 100 / denominator, 2) if denominator else None,
    }


def accuracy_report(session: Session, user: User) -> tuple[list[dict], list[dict]]:
    rows = session.execute(
        select(ReviewField, Shipment.supplier)
        .join(ShipmentDocument, ShipmentDocument.id == ReviewField.document_id)
        .join(Shipment, Shipment.id == ShipmentDocument.shipment_id)
    ).all()
    fields = [row[0] for row in rows]
    revisions = session.scalars(
        select(FieldRevision).where(FieldRevision.field_id.in_([field.id for field in fields]))
    ).all() if fields else []
    corrected_field_ids = {revision.field_id for revision in revisions if revision.action == ReviewAction.CORRECTED.value}
    field_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"confirmed_count": 0, "corrected_count": 0, "rejected_count": 0})
    supplier_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"confirmed_count": 0, "corrected_count": 0, "rejected_count": 0})
    supplier_by_field = {field.id: supplier for field, supplier in rows}
    for field in fields:
        bucket = field_counts[field.field_path]
        supplier_bucket = supplier_counts[supplier_by_field[field.id]]
        if field.status == ReviewFieldStatus.REJECTED.value:
            bucket["rejected_count"] += 1
            supplier_bucket["rejected_count"] += 1
        elif field.id in corrected_field_ids:
            bucket["corrected_count"] += 1
            supplier_bucket["corrected_count"] += 1
        elif field.status == ReviewFieldStatus.CONFIRMED.value:
            bucket["confirmed_count"] += 1
            supplier_bucket["confirmed_count"] += 1
    return (
        [_metric(key, counts) for key, counts in sorted(field_counts.items())],
        [_metric(key, counts) for key, counts in sorted(supplier_counts.items())],
    )
