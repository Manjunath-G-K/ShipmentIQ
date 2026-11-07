"""Stable field paths used by review, corrections, validation, and reporting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.models import DocumentType
from app.modules.extraction.schemas import ExtractionResult


@dataclass(frozen=True)
class FieldSnapshot:
    path: str
    value_type: str
    value: Any
    confidence: float | None
    sources: list[dict]


def _snapshot(path: str, value_type: str, value: dict) -> FieldSnapshot:
    return FieldSnapshot(
        path=path,
        value_type=value_type,
        value=value.get("value"),
        confidence=value.get("confidence"),
        sources=value.get("sources", []),
    )


def flatten_extraction(result: ExtractionResult) -> list[FieldSnapshot]:
    """Flatten the strict extraction tree without dropping null/missing fields."""

    payload = result.model_dump(mode="json")
    fields: list[FieldSnapshot] = []
    party_paths = {
        DocumentType.INVOICE: ("importer", "supplier"),
        DocumentType.PACKING_LIST: ("exporter", "consignee"),
        DocumentType.BILL_OF_LADING: ("exporter", "consignee"),
    }[result.document_type]
    for path in party_paths:
        fields.append(_snapshot(f"parties.{path}", "string", payload["parties"][path]))
    if result.document_type == DocumentType.INVOICE:
        fields.extend(
            [
                _snapshot("invoice.number", "string", payload["invoice"]["number"]),
                _snapshot("invoice.date", "date", payload["invoice"]["date"]),
                _snapshot("invoice.currency", "string", payload["invoice"]["currency"]),
                _snapshot("invoice.incoterm", "string", payload["invoice"]["incoterm"]),
                _snapshot("invoice.total", "decimal", payload["invoice"]["total"]),
            ]
        )
    fields.append(_snapshot("shipment.packages", "integer", payload["shipment"]["packages"]))
    fields.append(_snapshot("shipment.gross_weight_kg", "decimal", payload["shipment"]["gross_weight_kg"]))
    if result.document_type != DocumentType.BILL_OF_LADING:
        fields.append(_snapshot("shipment.net_weight_kg", "decimal", payload["shipment"]["net_weight_kg"]))
    for index, item in enumerate(payload["line_items"]):
        for path, value_type in (
            ("description", "string"),
            ("quantity", "decimal"),
            ("unit_price", "decimal"),
            ("hsn_code", "string"),
        ):
            fields.append(_snapshot(f"line_items[{index}].{path}", value_type, item[path]))
    for index, item in enumerate(payload["shipment"]["containers"]):
        fields.append(_snapshot(f"shipment.containers[{index}]", "string", item))
    return fields


def validation_paths() -> tuple[str, ...]:
    return (
        "shipment.packages",
        "shipment.gross_weight_kg",
        "shipment.net_weight_kg",
    )
