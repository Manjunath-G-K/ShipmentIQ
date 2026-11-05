"""Unit tests for review flags and deterministic validation rules."""

from uuid import uuid4

from app.db.models import DocumentType, ReviewField, ReviewFieldStatus, ShipmentDocument, ValidationStatus
from app.modules.review.service import (
    _field_flags,
    _invoice_total_validation,
    _validation_details,
    _validate_value,
)


def _field(document_id, path, value, value_type="decimal", status=ReviewFieldStatus.NEEDS_REVIEW.value):
    return ReviewField(
        document_id=document_id,
        field_path=path,
        value_type=value_type,
        extracted_value=value,
        current_value=value,
        confidence=0.9,
        source_references=[{"page": 1, "locator": "test"}],
        status=status,
        version=1,
    )


def test_invoice_total_validation_is_exact_and_does_not_choose_a_winner() -> None:
    document_id = uuid4()
    fields = {
        "invoice.total": _field(document_id, "invoice.total", "16.32"),
        "line_items[0].quantity": _field(document_id, "line_items[0].quantity", "2"),
        "line_items[0].unit_price": _field(document_id, "line_items[0].unit_price", "8.16"),
    }
    document = ShipmentDocument(id=document_id, document_type=DocumentType.INVOICE.value)

    status, details = _invoice_total_validation([document], {document_id: fields})

    assert status == ValidationStatus.PASSED
    assert details["invoice_total"] == "16.32"
    assert details["line_item_total"] == "16.32"

    fields["line_items[0].unit_price"].current_value = "8.17"
    status, details = _invoice_total_validation([document], {document_id: fields})
    assert status == ValidationStatus.FAILED
    assert details["comparison"] == "different"
    assert "winner" not in details


def test_cross_document_comparison_stays_unresolved_when_data_is_unavailable() -> None:
    invoice_id = uuid4()
    packing_id = uuid4()
    documents = [
        ShipmentDocument(id=invoice_id, document_type=DocumentType.INVOICE.value),
        ShipmentDocument(id=packing_id, document_type=DocumentType.PACKING_LIST.value),
    ]

    status, details = _validation_details(
        "shipment.gross_weight_kg",
        documents,
        {invoice_id: {"shipment.gross_weight_kg": _field(invoice_id, "shipment.gross_weight_kg", "3120")}, packing_id: {}},
    )

    assert status == ValidationStatus.UNRESOLVED
    assert details["comparison"] == "unavailable"


def test_review_flags_cover_missing_low_confidence_and_unreadable_pages() -> None:
    field = _field(uuid4(), "invoice.number", None, value_type="string")
    field.confidence = None
    extraction = type("Extraction", (), {"result": {"pages": [{"page": 2, "readable": False}]}})()

    flags = _field_flags(field, extraction, 0.8)

    assert flags == ["MISSING", "NEEDS_CONFIRMATION", "LOW_CONFIDENCE", "UNREADABLE_PAGE"]


def test_correction_value_validation_is_type_safe() -> None:
    field = _field(uuid4(), "shipment.packages", 2, value_type="integer")

    assert _validate_value(field, 4) == 4

    try:
        _validate_value(field, "four")
    except Exception as exc:
        assert getattr(exc, "code", None) == "INVALID_FIELD_VALUE"
    else:
        raise AssertionError("invalid correction should be rejected")
