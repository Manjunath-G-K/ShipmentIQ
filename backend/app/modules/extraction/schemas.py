"""Strict schemas for OCR provenance and extracted document values."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import DocumentType


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    locator: str = Field(min_length=1, max_length=160)


class OCRPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    text: str = Field(max_length=200_000)
    readable: bool
    source: Literal["embedded_text", "ocr", "unreadable"]


class ExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence: float | None = Field(default=None, ge=0, le=1)
    sources: list[SourceReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def extracted_values_need_evidence(self):
        if getattr(self, "value", None) is not None and (self.confidence is None or not self.sources):
            raise ValueError("an extracted value requires confidence and source references")
        return self


class ExtractedString(ExtractedField):
    value: str | None = None


class ExtractedInteger(ExtractedField):
    value: int | None = None


class ExtractedDecimal(ExtractedField):
    value: Decimal | None = None


class ExtractedDate(ExtractedField):
    value: date | None = None


class PartyFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    importer: ExtractedString = Field(default_factory=ExtractedString)
    supplier: ExtractedString = Field(default_factory=ExtractedString)
    consignee: ExtractedString = Field(default_factory=ExtractedString)
    exporter: ExtractedString = Field(default_factory=ExtractedString)


class InvoiceFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: ExtractedString = Field(default_factory=ExtractedString)
    date: ExtractedDate = Field(default_factory=ExtractedDate)
    currency: ExtractedString = Field(default_factory=ExtractedString)
    incoterm: ExtractedString = Field(default_factory=ExtractedString)
    total: ExtractedDecimal = Field(default_factory=ExtractedDecimal)


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: ExtractedString = Field(default_factory=ExtractedString)
    quantity: ExtractedDecimal = Field(default_factory=ExtractedDecimal)
    unit_price: ExtractedDecimal = Field(default_factory=ExtractedDecimal)
    hsn_code: ExtractedString = Field(default_factory=ExtractedString)


class ShipmentFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packages: ExtractedInteger = Field(default_factory=ExtractedInteger)
    gross_weight_kg: ExtractedDecimal = Field(default_factory=ExtractedDecimal)
    net_weight_kg: ExtractedDecimal = Field(default_factory=ExtractedDecimal)
    containers: list[ExtractedString] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """The only shape accepted from an extraction provider."""

    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    pages: list[OCRPage] = Field(default_factory=list)
    parties: PartyFields = Field(default_factory=PartyFields)
    invoice: InvoiceFields = Field(default_factory=InvoiceFields)
    line_items: list[LineItem] = Field(default_factory=list)
    shipment: ShipmentFields = Field(default_factory=ShipmentFields)

    @field_validator("pages")
    @classmethod
    def pages_are_ordered(cls, value: list[OCRPage]) -> list[OCRPage]:
        pages = [page.page for page in value]
        if pages != sorted(set(pages)):
            raise ValueError("pages must be unique and ordered")
        return value

    def has_missing_values(self) -> bool:
        if self.document_type == DocumentType.INVOICE:
            fields = [
                self.parties.importer,
                self.parties.supplier,
                self.invoice.number,
                self.invoice.date,
                self.invoice.currency,
                self.invoice.incoterm,
                self.invoice.total,
                self.shipment.packages,
                self.shipment.gross_weight_kg,
                self.shipment.net_weight_kg,
            ]
        elif self.document_type == DocumentType.PACKING_LIST:
            fields = [
                self.parties.exporter,
                self.parties.consignee,
                self.shipment.packages,
                self.shipment.gross_weight_kg,
                self.shipment.net_weight_kg,
            ]
        else:
            fields = [
                self.parties.exporter,
                self.parties.consignee,
                self.shipment.packages,
                self.shipment.gross_weight_kg,
            ]
        return any(field.value is None for field in fields)


def normalize_json_provider_payload(raw: Any) -> dict:
    """Normalize only JSON-native representations before strict validation.

    JSON has no enum, date, or Decimal types. These conversions are explicit and
    narrow; confidence, source, and field structure remain strict Pydantic inputs.
    """

    if isinstance(raw, ExtractionResult):
        return raw.model_dump()
    if not isinstance(raw, dict):
        raise TypeError("provider response must be a JSON object")
    payload = dict(raw)
    if isinstance(payload.get("document_type"), str):
        payload["document_type"] = DocumentType(payload["document_type"])

    def normalize_field(field: Any, value_type: str) -> None:
        if not isinstance(field, dict) or field.get("value") is None:
            return
        value = field["value"]
        if value_type == "decimal":
            if isinstance(value, bool):
                raise TypeError("boolean is not a decimal")
            field["value"] = Decimal(str(value))
        elif value_type == "date" and isinstance(value, str):
            field["value"] = date.fromisoformat(value)

    parties = payload.get("parties", {})
    for key in ("importer", "supplier", "consignee", "exporter"):
        normalize_field(parties.get(key), "string")
    invoice = payload.get("invoice", {})
    for key in ("number", "currency", "incoterm"):
        normalize_field(invoice.get(key), "string")
    normalize_field(invoice.get("date"), "date")
    normalize_field(invoice.get("total"), "decimal")
    shipment = payload.get("shipment", {})
    normalize_field(shipment.get("packages"), "integer")
    for key in ("gross_weight_kg", "net_weight_kg"):
        normalize_field(shipment.get(key), "decimal")
    for item in payload.get("line_items", []):
        if isinstance(item, dict):
            normalize_field(item.get("quantity"), "decimal")
            normalize_field(item.get("unit_price"), "decimal")
            normalize_field(item.get("description"), "string")
            normalize_field(item.get("hsn_code"), "string")
    for item in shipment.get("containers", []):
        normalize_field(item, "string")
    return payload
