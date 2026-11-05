"""Backend-enforced eligibility and provisional CSV generation."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ExportBlockedError, ShipmentNotFoundError
from app.db.models import (
    DocumentExtraction,
    DocumentType,
    ReviewField,
    ReviewFieldStatus,
    Shipment,
    ShipmentDocument,
    ShipmentStatus,
    ShipmentValidation,
    User,
    ValidationStatus,
)
from app.modules.exports.schemas import PROVISIONAL_EXPORT_COLUMNS
from app.modules.review.service import VALIDATION_RULES, _get_shipment_for_user


def _blocker(code: str, message: str, **extra: Any) -> dict:
    return {"code": code, "message": message, **extra}


def _required_paths(document_type: str) -> set[str]:
    if document_type == DocumentType.INVOICE.value:
        return {
            "parties.importer",
            "parties.supplier",
            "invoice.number",
            "invoice.date",
            "invoice.currency",
            "invoice.incoterm",
            "invoice.total",
            "shipment.packages",
            "shipment.gross_weight_kg",
            "shipment.net_weight_kg",
        }
    if document_type in {DocumentType.PACKING_LIST.value, DocumentType.BILL_OF_LADING.value}:
        return {
            "shipment.packages",
            "shipment.gross_weight_kg",
            "shipment.net_weight_kg",
        }
    return set()


def _load_export_state(session: Session, user: User, shipment_id: UUID, *, lock_shipment: bool = False):
    shipment = _get_shipment_for_user(session, user, shipment_id)
    if lock_shipment:
        shipment = session.scalar(
            select(Shipment).where(Shipment.id == shipment.id).with_for_update()
        )
        if shipment is None:
            # The access-scoped lookup above already guarantees this in normal use;
            # keeping the guard makes the locked read explicit and defensive.
            raise ShipmentNotFoundError()
    documents = session.scalars(
        select(ShipmentDocument)
        .where(ShipmentDocument.shipment_id == shipment.id)
        .order_by(ShipmentDocument.document_type, ShipmentDocument.id)
    ).all()
    document_ids = [document.id for document in documents]
    extractions = session.scalars(
        select(DocumentExtraction).where(DocumentExtraction.document_id.in_(document_ids))
    ).all() if document_ids else []
    fields = session.scalars(
        select(ReviewField).where(ReviewField.document_id.in_(document_ids))
    ).all() if document_ids else []
    validations = session.scalars(
        select(ShipmentValidation).where(ShipmentValidation.shipment_id == shipment.id)
    ).all()
    return shipment, documents, {item.document_id: item for item in extractions}, fields, validations


def export_eligibility(
    session: Session,
    user: User,
    shipment_id: UUID,
    low_confidence_threshold: float,
) -> dict:
    shipment, documents, extractions, fields, validations = _load_export_state(session, user, shipment_id)
    blockers: list[dict] = []
    if not any(document.document_type == DocumentType.INVOICE.value for document in documents):
        blockers.append(_blocker("INVOICE_DOCUMENT_REQUIRED", "An invoice is required for the provisional export"))

    fields_by_document: dict[UUID, dict[str, ReviewField]] = {}
    for field in fields:
        fields_by_document.setdefault(field.document_id, {})[field.field_path] = field

    for document in documents:
        extraction = extractions.get(document.id)
        if extraction is None:
            blockers.append(_blocker("EXTRACTION_REQUIRED", "Document extraction has not completed", document_id=document.id))
            continue
        if extraction.status == "FAILED":
            blockers.append(_blocker("EXTRACTION_FAILED", "Document processing failed", document_id=document.id))
        if extraction.result and any(not page.get("readable", False) for page in extraction.result.get("pages", [])):
            blockers.append(_blocker("UNREADABLE_PAGE", "All document pages must be readable", document_id=document.id))
        field_map = fields_by_document.get(document.id, {})
        required = _required_paths(document.document_type)
        if document.document_type == DocumentType.INVOICE and not any(path.startswith("line_items[") and path.endswith(".quantity") for path in field_map):
            blockers.append(_blocker("LINE_ITEMS_REQUIRED", "The invoice must contain at least one line item", document_id=document.id))
        for path in required:
            field = field_map.get(path)
            if field is None or field.current_value is None:
                blockers.append(_blocker("MISSING_REQUIRED_FIELD", "Required field is missing", field_id=field.id if field else None, field_path=path, document_id=document.id))
        for field in field_map.values():
            if field.status == ReviewFieldStatus.REJECTED.value:
                blockers.append(_blocker("REJECTED_FIELD", "Rejected fields cannot be exported", field_id=field.id, field_path=field.field_path, document_id=document.id))
            if field.current_value is not None:
                if field.confidence is None or float(field.confidence) < low_confidence_threshold:
                    blockers.append(_blocker("LOW_CONFIDENCE_FIELD", "Low-confidence fields must be reviewed", field_id=field.id, field_path=field.field_path, document_id=document.id))
                if field.status != ReviewFieldStatus.CONFIRMED.value:
                    blockers.append(_blocker("UNCONFIRMED_FIELD", "Fields must be human-confirmed before export", field_id=field.id, field_path=field.field_path, document_id=document.id))

    validation_map = {validation.rule_key: validation for validation in validations}
    for rule_key in VALIDATION_RULES:
        validation = validation_map.get(rule_key)
        if validation is None:
            blockers.append(_blocker("VALIDATION_NOT_RUN", "All validation checks must pass before export", rule_key=rule_key))
        elif validation.status != ValidationStatus.PASSED.value:
            blockers.append(_blocker("VALIDATION_NOT_PASSED", "Validation must be rerun and pass before export", rule_key=rule_key))
    return {"eligible": not blockers, "blockers": blockers}


def _value(fields: dict[str, ReviewField], path: str) -> Any:
    field = fields.get(path)
    return "" if field is None or field.current_value is None else field.current_value


def generate_csv(
    session: Session,
    user: User,
    shipment_id: UUID,
    low_confidence_threshold: float,
) -> str:
    # Hold the shipment row lock for the eligibility read and CSV snapshot. A
    # concurrent correction therefore serializes before or after a complete
    # export decision instead of allowing a mixed/stale snapshot.
    _load_export_state(session, user, shipment_id, lock_shipment=True)
    eligibility = export_eligibility(session, user, shipment_id, low_confidence_threshold)
    if not eligibility["eligible"]:
        raise ExportBlockedError(eligibility["blockers"])
    shipment, documents, _extractions, fields, _validations = _load_export_state(
        session, user, shipment_id, lock_shipment=True
    )
    invoice = next(document for document in documents if document.document_type == DocumentType.INVOICE.value)
    invoice_fields = {field.field_path: field for field in fields if field.document_id == invoice.id}
    line_indexes = sorted({int(path.split("[")[1].split("]")[0]) for path in invoice_fields if path.startswith("line_items[")})
    containers = [field.current_value for field in invoice_fields.values() if field.field_path.startswith("shipment.containers[") and field.current_value is not None]
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=PROVISIONAL_EXPORT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for index in line_indexes:
        writer.writerow({
            "shipment_reference": shipment.shipment_reference,
            "importer": _value(invoice_fields, "parties.importer"),
            "supplier": _value(invoice_fields, "parties.supplier"),
            "origin_country": shipment.origin_country,
            "invoice_number": _value(invoice_fields, "invoice.number"),
            "invoice_date": _value(invoice_fields, "invoice.date"),
            "currency": _value(invoice_fields, "invoice.currency"),
            "incoterm": _value(invoice_fields, "invoice.incoterm"),
            "invoice_total": _value(invoice_fields, "invoice.total"),
            "item_description": _value(invoice_fields, f"line_items[{index}].description"),
            "quantity": _value(invoice_fields, f"line_items[{index}].quantity"),
            "unit_price": _value(invoice_fields, f"line_items[{index}].unit_price"),
            "hsn_code": _value(invoice_fields, f"line_items[{index}].hsn_code"),
            "packages": _value(invoice_fields, "shipment.packages"),
            "gross_weight_kg": _value(invoice_fields, "shipment.gross_weight_kg"),
            "net_weight_kg": _value(invoice_fields, "shipment.net_weight_kg"),
            "containers": "; ".join(str(container) for container in containers),
        })
    shipment.status = ShipmentStatus.EXPORTED.value
    session.commit()
    return output.getvalue()
