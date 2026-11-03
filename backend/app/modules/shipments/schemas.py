"""Validated shipment request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import ShipmentStatus


def _required_text(value: str, field_name: str, max_length: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return normalized


class ShipmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_reference: str = Field(min_length=1, max_length=64)
    importer: str = Field(min_length=1, max_length=255)
    supplier: str = Field(min_length=1, max_length=255)
    origin_country: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("shipment_reference")
    @classmethod
    def normalize_reference(cls, value: str) -> str:
        return _required_text(value, "shipment_reference", 64).upper()

    @field_validator("importer")
    @classmethod
    def normalize_importer(cls, value: str) -> str:
        return _required_text(value, "importer", 255)

    @field_validator("supplier")
    @classmethod
    def normalize_supplier(cls, value: str) -> str:
        return _required_text(value, "supplier", 255)

    @field_validator("origin_country")
    @classmethod
    def normalize_origin_country(cls, value: str) -> str:
        return _required_text(value, "origin_country", 100)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() if value is not None and value.strip() else None


class ShipmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_reference: str | None = Field(default=None, min_length=1, max_length=64)
    importer: str | None = Field(default=None, min_length=1, max_length=255)
    supplier: str | None = Field(default=None, min_length=1, max_length=255)
    origin_country: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_update_field(self) -> "ShipmentUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one shipment field must be provided")
        return self

    @field_validator("shipment_reference")
    @classmethod
    def normalize_reference(cls, value: str | None) -> str | None:
        return _required_text(value, "shipment_reference", 64).upper() if value is not None else None

    @field_validator("importer")
    @classmethod
    def normalize_importer(cls, value: str | None) -> str | None:
        return _required_text(value, "importer", 255) if value is not None else None

    @field_validator("supplier")
    @classmethod
    def normalize_supplier(cls, value: str | None) -> str | None:
        return _required_text(value, "supplier", 255) if value is not None else None

    @field_validator("origin_country")
    @classmethod
    def normalize_origin_country(cls, value: str | None) -> str | None:
        return _required_text(value, "origin_country", 100) if value is not None else None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() if value is not None and value.strip() else None


class ShipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shipment_reference: str
    importer: str
    supplier: str
    origin_country: str
    description: str | None
    status: ShipmentStatus
    created_at: datetime
    updated_at: datetime


class ShipmentListResponse(BaseModel):
    items: list[ShipmentResponse]
    total: int
    limit: int
    offset: int
