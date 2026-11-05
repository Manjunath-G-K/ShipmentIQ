"""API schemas for human review, validation, and accuracy reporting."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.db.models import DocumentType, ReviewFieldStatus, ValidationStatus
from app.modules.extraction.schemas import SourceReference


class FieldCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: JsonValue | None = None
    note: str | None = Field(default=None, max_length=500)
    expected_version: int = Field(default=1, ge=1)


class ReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=500)
    expected_version: int = Field(default=1, ge=1)


class RevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    field_id: UUID
    actor_id: UUID
    action: str
    previous_value: JsonValue | None
    new_value: JsonValue | None
    note: str | None
    created_at: datetime


class ReviewFieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    field_path: str
    value_type: str
    value: JsonValue | None
    extracted_value: JsonValue | None
    confidence: float | None
    source_references: list[SourceReference]
    status: ReviewFieldStatus
    version: int
    flags: list[str]
    last_reviewed_by_id: UUID | None
    last_reviewed_at: datetime | None


class ReviewDocumentResponse(BaseModel):
    id: UUID
    document_type: DocumentType
    extraction_status: str | None
    extraction_error_code: str | None
    page_count: int
    fields: list[ReviewFieldResponse]


class ValidationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shipment_id: UUID
    rule_key: str
    status: ValidationStatus
    details: dict
    evaluated_by_id: UUID
    evaluated_at: datetime


class ReviewResponse(BaseModel):
    shipment_id: UUID
    documents: list[ReviewDocumentResponse]
    validations: list[ValidationResponse]


class ValidationRunResponse(BaseModel):
    shipment_id: UUID
    validations: list[ValidationResponse]


class AccuracyMetric(BaseModel):
    key: str
    reviewed_count: int
    confirmed_count: int
    corrected_count: int
    rejected_count: int
    accuracy_percent: float | None


class AccuracyReportResponse(BaseModel):
    field_metrics: list[AccuracyMetric]
    supplier_metrics: list[AccuracyMetric]
