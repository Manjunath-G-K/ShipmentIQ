"""CSV export eligibility response schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExportBlocker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    field_id: UUID | None = None
    field_path: str | None = None
    rule_key: str | None = None
    document_id: UUID | None = None


class ExportEligibilityResponse(BaseModel):
    eligible: bool
    blockers: list[ExportBlocker]


PROVISIONAL_EXPORT_COLUMNS = [
    "shipment_reference",
    "importer",
    "supplier",
    "origin_country",
    "invoice_number",
    "invoice_date",
    "currency",
    "incoterm",
    "invoice_total",
    "item_description",
    "quantity",
    "unit_price",
    "hsn_code",
    "packages",
    "gross_weight_kg",
    "net_weight_kg",
    "containers",
]
