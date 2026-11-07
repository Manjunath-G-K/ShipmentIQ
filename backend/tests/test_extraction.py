"""Unit tests for strict extraction contracts and the free local provider."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import sys

import pytest
from pydantic import ValidationError

from app.db.models import DocumentType
from app.modules.extraction.providers import LocalRuleBasedProvider
from app.modules.extraction.providers import LocalOCRProvider
from app.modules.extraction.schemas import ExtractionResult, OCRPage, normalize_json_provider_payload
from app.modules.review.field_map import flatten_extraction


def test_local_provider_extracts_explicit_values_with_page_provenance() -> None:
    pages = [
        OCRPage(page=1, text="Supplier: Synthetic Supplier\nInvoice No: INV-42", readable=True, source="embedded_text"),
        OCRPage(page=2, text=(
            "Invoice Date: 2026-11-05\nCurrency: USD\nIncoterm: FOB\n"
            "Importer: Synthetic Importer\nPackages: 12\nGross Weight (kg): 3120\n"
            "Net Weight (kg): 3000\nLED panel light 40W | 2400 | 6.80 | 9405\n"
            "Invoice Total: 16320\nContainer: MSKU1234567"
        ), readable=True, source="embedded_text"),
    ]

    result = LocalRuleBasedProvider().extract(pages, DocumentType.INVOICE)

    assert result.invoice.number.value == "INV-42"
    assert result.invoice.date.value == date(2026, 11, 5)
    assert result.invoice.date.sources[0].page == 2
    assert result.shipment.gross_weight_kg.value == Decimal("3120")
    assert result.shipment.gross_weight_kg.sources[0].page == 2
    assert result.invoice.total.value == Decimal("16320")
    assert result.line_items[0].hsn_code.value == "9405"
    assert result.line_items[0].quantity.sources[0].page == 2
    assert result.shipment.containers[0].value == "MSKU1234567"
    assert result.shipment.containers[0].confidence == 0.9


def test_missing_values_are_null_and_marked_for_review() -> None:
    result = LocalRuleBasedProvider().extract(
        [OCRPage(page=1, text="Supplier: Only Supplier", readable=True, source="ocr")],
        DocumentType.PACKING_LIST,
    )

    assert result.invoice.number.value is None
    assert result.invoice.number.confidence is None
    assert result.has_missing_values()


def test_strict_schema_rejects_unknown_provider_fields_and_bad_confidence() -> None:
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(
            {
                "document_type": "INVOICE",
                "invoice": {"currency": {"value": "USD", "confidence": 2.0}},
                "unexpected": "must fail",
            },
            strict=True,
        )


def test_json_ai_payload_normalizes_json_scalars_then_validates_strictly() -> None:
    payload = {
        "document_type": "INVOICE",
        "invoice": {
            "date": {"value": "2026-11-05", "confidence": 0.9, "sources": [{"page": 1, "locator": "date"}]},
            "total": {"value": "16.32", "confidence": 0.9, "sources": [{"page": 1, "locator": "total"}]},
        },
    }

    result = ExtractionResult.model_validate(
        normalize_json_provider_payload(payload), strict=True
    )

    assert result.invoice.date.value == date(2026, 11, 5)
    assert result.invoice.total.value == Decimal("16.32")


def test_local_ocr_uses_embedded_text_before_scanned_ocr(monkeypatch) -> None:
    class EmbeddedPage:
        def extract_text(self):
            return "embedded synthetic text"

    class EmbeddedReader:
        pages = [EmbeddedPage()]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=lambda _: EmbeddedReader()))
    monkeypatch.setattr(
        LocalOCRProvider,
        "_ocr_pdf_page",
        lambda *_args: (_ for _ in ()).throw(AssertionError("scanned OCR should not run")),
    )

    pages = LocalOCRProvider().extract(b"synthetic-pdf", "application/pdf")

    assert pages == [
        OCRPage(page=1, text="embedded synthetic text", readable=True, source="embedded_text")
    ]


def test_local_provider_extracts_table_layout_for_all_synthetic_document_types() -> None:
    provider = LocalRuleBasedProvider()
    invoice_text = """Document reference: BPR-INV-26-073    Shipment reference: SHP-2026-003
Seller / Exporter
Company
Address
BluePeak Renewable Components Pvt Ltd
Buyer / Importer
Company
Address
Asterion Energy Solutions Pvt Ltd
Invoice date
Currency
Origin
Destination
06 November 2026
INR
India
India
Goods description
Line
Description
Quantity
Unit price
Line total
1
Solar inverter control boards
80 pcs
INR 8,500.00
INR 680,000.00
2
Battery management units
40 pcs
INR 12,000.00
INR 480,000.00
TOTAL
120 pcs
INR 1,160,000.00
Shipment details
Packages
Net weight
Gross weight
Delivery terms
12 cartons
2,180 kg
2,450 kg
DAP Pune"""
    packing_text = """Document reference: BPR-PL-26-073    Shipment reference: SHP-2026-003
Exporter / Consignee
Exporter
Consignee
BluePeak Renewable Components Pvt Ltd<br/>Survey 44
Asterion Energy Solutions Pvt Ltd<br/>Warehouse 7
Packing date
Invoice reference
Shipment
06 November 2026
BPR-INV-26-073
SHP-2026-003
Weight summary
Packages
Net weight
Gross weight
Dimensions
12 cartons
2,180 kg
2,490 kg
Not stated"""
    bol_text = """Document reference: BPR-BOL-26-073    Shipment reference: SHP-2026-003
Shipper / Consignee
Shipper
Consignee
BluePeak Renewable Components Pvt Ltd<br/>Survey 44
Asterion Energy Solutions Pvt Ltd<br/>Warehouse 7
Cargo description
Packages
Description
Gross weight
Marks
12 cartons
Solar inverter control boards and battery management units
2,450 kg
BP-001 to BP-012"""

    invoice = provider.extract([OCRPage(page=1, text=invoice_text, readable=True, source="embedded_text")], DocumentType.INVOICE)
    packing = provider.extract([OCRPage(page=1, text=packing_text, readable=True, source="embedded_text")], DocumentType.PACKING_LIST)
    bol = provider.extract([OCRPage(page=1, text=bol_text, readable=True, source="embedded_text")], DocumentType.BILL_OF_LADING)

    assert invoice.invoice.number.value == "BPR-INV-26-073"
    assert invoice.invoice.date.value == date(2026, 11, 6)
    assert invoice.invoice.currency.value == "INR"
    assert invoice.invoice.incoterm.value == "DAP"
    assert invoice.invoice.total.value == Decimal("1160000.00")
    assert len(invoice.line_items) == 2
    assert invoice.shipment.gross_weight_kg.value == Decimal("2450")
    assert invoice.shipment.gross_weight_kg.sources[0].page == 1
    assert not invoice.has_missing_values()

    assert packing.parties.exporter.value == "BluePeak Renewable Components Pvt Ltd"
    assert packing.parties.consignee.value == "Asterion Energy Solutions Pvt Ltd"
    assert packing.shipment.gross_weight_kg.value == Decimal("2490")
    assert not packing.has_missing_values()

    assert bol.invoice.number.value is None
    assert bol.shipment.gross_weight_kg.value == Decimal("2450")
    assert not bol.has_missing_values()
    assert not any(field.path.startswith("invoice.") for field in flatten_extraction(bol))
    assert not any(field.path == "shipment.net_weight_kg" for field in flatten_extraction(bol))
