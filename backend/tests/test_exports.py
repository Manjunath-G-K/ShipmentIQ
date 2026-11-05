from app.db.models import DocumentType
from app.modules.exports.schemas import PROVISIONAL_EXPORT_COLUMNS
from app.modules.exports.service import _required_paths


def test_provisional_export_layout_is_explicit_and_line_item_ready():
    assert PROVISIONAL_EXPORT_COLUMNS[0] == "shipment_reference"
    assert "item_description" in PROVISIONAL_EXPORT_COLUMNS
    assert "hsn_code" in PROVISIONAL_EXPORT_COLUMNS
    assert PROVISIONAL_EXPORT_COLUMNS[-1] == "containers"


def test_export_required_paths_are_conservative_by_document_type():
    invoice_paths = _required_paths(DocumentType.INVOICE.value)
    assert {"invoice.number", "invoice.date", "invoice.currency", "invoice.incoterm"}.issubset(invoice_paths)
    assert {"shipment.packages", "shipment.gross_weight_kg", "shipment.net_weight_kg"}.issubset(invoice_paths)
    assert _required_paths("OTHER") == set()
