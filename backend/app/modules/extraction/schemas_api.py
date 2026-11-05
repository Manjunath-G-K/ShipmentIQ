"""API response schemas for persisted extraction runs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models import ExtractionStatus
from app.modules.extraction.schemas import ExtractionResult


class ExtractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    status: ExtractionStatus
    provider_name: str
    ocr_provider_name: str
    page_count: int
    result: ExtractionResult | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
