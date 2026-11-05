"""Stable field paths used by review, corrections, validation, and reporting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    for path in ("importer", "supplier", "consignee", "exporter"):
        fields.append(_snapshot(f"parties.{path}", "string", payload["parties"][path]))
    fields.extend(
        [
            _snapshot("invoice.number", "string", payload["invoice"]["number"]),
            _snapshot("invoice.date", "date", payload["invoice"]["date"]),
            _snapshot("invoice.currency", "string", payload["invoice"]["currency"]),
            _snapshot("invoice.incoterm", "string", payload["invoice"]["incoterm"]),
            _snapshot("invoice.total", "decimal", payload["invoice"]["total"]),
            _snapshot("shipment.packages", "integer", payload["shipment"]["packages"]),
            _snapshot("shipment.gross_weight_kg", "decimal", payload["shipment"]["gross_weight_kg"]),
            _snapshot("shipment.net_weight_kg", "decimal", payload["shipment"]["net_weight_kg"]),
        ]
    )
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
