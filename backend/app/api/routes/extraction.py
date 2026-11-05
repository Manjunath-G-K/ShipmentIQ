"""Authorized OCR and structured extraction endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_allowed_origin, require_any_role, require_csrf
from app.core.config import Settings, get_settings
from app.db.models import RoleName, User
from app.db.session import get_db
from app.modules.documents.storage import PrivateFileStorage
from app.modules.extraction.api import get_ai_provider, get_ocr_provider
from app.modules.extraction.schemas_api import ExtractionResponse
from app.modules.extraction.service import get_extraction, process_extraction

router = APIRouter(prefix="/shipments/{shipment_id}/documents", tags=["extraction"])
ShipmentUser = Annotated[User, Depends(require_any_role(RoleName.DOCUMENTATION_EXECUTIVE, RoleName.DOCUMENTATION_MANAGER))]


def get_document_storage(settings: Annotated[Settings, Depends(get_settings)]) -> PrivateFileStorage:
    return PrivateFileStorage(settings.document_storage_path, settings.document_max_size_bytes)


@router.post("/{document_id}/extract", response_model=ExtractionResponse, status_code=status.HTTP_200_OK, dependencies=[Depends(require_allowed_origin), Depends(require_csrf)])
def extract(
    shipment_id: UUID,
    document_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    user: ShipmentUser,
    storage: Annotated[PrivateFileStorage, Depends(get_document_storage)],
    ocr_provider=Depends(get_ocr_provider),
    ai_provider=Depends(get_ai_provider),
) -> ExtractionResponse:
    return ExtractionResponse.model_validate(process_extraction(session, user, shipment_id, document_id, storage, ocr_provider, ai_provider))


@router.get("/{document_id}/extraction", response_model=ExtractionResponse)
def read_extraction(
    shipment_id: UUID,
    document_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    user: ShipmentUser,
) -> ExtractionResponse:
    return ExtractionResponse.model_validate(get_extraction(session, user, shipment_id, document_id))
