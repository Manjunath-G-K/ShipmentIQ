from app.db.models import DocumentType, ReviewField, ReviewFieldStatus
from app.modules.exports.schemas import PROVISIONAL_EXPORT_COLUMNS
from app.modules.exports.service import _field_export_blockers, _required_paths


def test_provisional_export_layout_is_explicit_and_line_item_ready():
    assert PROVISIONAL_EXPORT_COLUMNS[0] == "shipment_reference"
    assert "item_description" in PROVISIONAL_EXPORT_COLUMNS
    assert "hsn_code" in PROVISIONAL_EXPORT_COLUMNS
    assert PROVISIONAL_EXPORT_COLUMNS[-1] == "containers"


def test_export_required_paths_are_conservative_by_document_type():
    invoice_paths = _required_paths(DocumentType.INVOICE.value)
    assert {"invoice.number", "invoice.date", "invoice.currency", "invoice.incoterm"}.issubset(invoice_paths)
    assert {"shipment.packages", "shipment.gross_weight_kg", "shipment.net_weight_kg"}.issubset(invoice_paths)
    assert "shipment.net_weight_kg" not in _required_paths(DocumentType.BILL_OF_LADING.value)
    assert _required_paths("OTHER") == set()


def _review_field(*, value, confidence, status):
    return ReviewField(
        document_id=None,
        field_path="invoice.currency",
        value_type="string",
        extracted_value=None,
        current_value=value,
        confidence=confidence,
        source_references=[],
        status=status,
        version=1,
    )


def test_confirmed_manual_value_is_not_blocked_by_original_low_confidence():
    field = _review_field(
        value="USD",
        confidence=None,
        status=ReviewFieldStatus.CONFIRMED.value,
    )

    assert _field_export_blockers(field, 0.8) == ()


def test_unreviewed_low_confidence_value_remains_blocked():
    field = _review_field(
        value="USD",
        confidence=0.2,
        status=ReviewFieldStatus.NEEDS_REVIEW.value,
    )

    assert _field_export_blockers(field, 0.8) == (
        "LOW_CONFIDENCE_FIELD",
        "UNCONFIRMED_FIELD",
    )


def test_rejected_value_remains_blocked():
    field = _review_field(
        value=None,
        confidence=0.95,
        status=ReviewFieldStatus.REJECTED.value,
    )

    assert _field_export_blockers(field, 0.8) == ("REJECTED_FIELD",)
