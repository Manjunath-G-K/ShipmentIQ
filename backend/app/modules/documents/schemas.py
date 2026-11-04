"""Validated shipment document API response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models import DocumentType


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_type: DocumentType
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
