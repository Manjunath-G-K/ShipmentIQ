"""Unit tests for strict extraction contracts and the free local provider."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.db.models import DocumentType
from app.modules.extraction.providers import LocalRuleBasedProvider
from app.modules.extraction.schemas import ExtractionResult, OCRPage, normalize_json_provider_payload


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
