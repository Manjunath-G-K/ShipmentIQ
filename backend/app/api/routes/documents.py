"""Private shipment document upload, listing, and download endpoints."""

from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.api.dependencies import (
    require_allowed_origin,
    require_any_role,
    require_csrf,
    require_role,
)
from app.core.config import Settings, get_settings
from app.db.models import DocumentType, RoleName, User
from app.db.session import get_db
from app.modules.documents.schemas import DocumentListResponse, DocumentResponse
from app.modules.documents.service import list_documents, open_document, upload_document
from app.modules.documents.storage import PrivateFileStorage


router = APIRouter(prefix="/shipments/{shipment_id}/documents", tags=["documents"])
ShipmentUser = Annotated[
    User,
    Depends(
        require_any_role(
            RoleName.DOCUMENTATION_EXECUTIVE, RoleName.DOCUMENTATION_MANAGER
        )
    ),
]
ExecutiveUser = Annotated[
    User, Depends(require_role(RoleName.DOCUMENTATION_EXECUTIVE))
]


def get_document_storage(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PrivateFileStorage:
    return PrivateFileStorage(
        settings.document_storage_path, settings.document_max_size_bytes
    )


def _response(document) -> DocumentResponse:
    return DocumentResponse.model_validate(document)


def _download_name(filename: str) -> str:
    basename = Path(filename).name.replace("\r", "").replace("\n", "")
    safe_ascii = "".join(
        character if character.isascii() and (character.isalnum() or character in ".-_ ") else "_"
        for character in basename
    ).strip()
    safe_ascii = safe_ascii[:150] or "document"
    return (
        f'attachment; filename="{safe_ascii}"; '
        f"filename*=UTF-8''{quote(basename, safe='')}"
    )


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_allowed_origin), Depends(require_csrf)],
)
def upload(
    shipment_id: UUID,
    document_type: Annotated[DocumentType, Form()],
    file: Annotated[UploadFile, File()],
    session: Annotated[Session, Depends(get_db)],
    user: ExecutiveUser,
    storage: Annotated[PrivateFileStorage, Depends(get_document_storage)],
) -> DocumentResponse:
    document = upload_document(
        session,
        user,
        shipment_id,
        document_type,
        file.file,
        filename=file.filename,
        declared_content_type=file.content_type,
        storage=storage,
    )
    return _response(document)


@router.get("", response_model=DocumentListResponse)
def list_all(
    shipment_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    user: ShipmentUser,
) -> DocumentListResponse:
    return DocumentListResponse(
        items=[_response(document) for document in list_documents(session, user, shipment_id)]
    )


@router.get("/{document_id}/download")
def download(
    shipment_id: UUID,
    document_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    user: ShipmentUser,
    storage: Annotated[PrivateFileStorage, Depends(get_document_storage)],
):
    document, file_object = open_document(
        session, user, shipment_id, document_id, storage
    )
    return StreamingResponse(
        iter(lambda: file_object.read(1024 * 1024), b""),
        media_type=document.content_type,
        headers={"Content-Disposition": _download_name(document.original_filename)},
        background=BackgroundTask(file_object.close),
    )
