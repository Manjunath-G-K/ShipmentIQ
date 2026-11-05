"""Backend-enforced provisional CSV export endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.dependencies import require_allowed_origin, require_any_role, require_csrf, require_role
from app.core.config import Settings, get_settings
from app.db.models import RoleName, User
from app.db.session import get_db
from app.modules.exports.schemas import ExportEligibilityResponse
from app.modules.exports.service import export_eligibility, generate_csv


router = APIRouter(tags=["exports"])
ShipmentUser = Annotated[
    User,
    Depends(require_any_role(RoleName.DOCUMENTATION_EXECUTIVE, RoleName.DOCUMENTATION_MANAGER)),
]
ExecutiveUser = Annotated[User, Depends(require_role(RoleName.DOCUMENTATION_EXECUTIVE))]


@router.get("/shipments/{shipment_id}/export-eligibility", response_model=ExportEligibilityResponse)
def eligibility(
    shipment_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    user: ShipmentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExportEligibilityResponse:
    return ExportEligibilityResponse.model_validate(
        export_eligibility(session, user, shipment_id, settings.extraction_low_confidence_threshold)
    )


@router.post(
    "/shipments/{shipment_id}/exports",
    dependencies=[Depends(require_allowed_origin), Depends(require_csrf)],
)
def export(
    shipment_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    user: ExecutiveUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    csv_data = generate_csv(session, user, shipment_id, settings.extraction_low_confidence_threshold)
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="shipment-{shipment_id}.csv"'},
    )
