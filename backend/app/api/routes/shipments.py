"""Shipment management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    require_allowed_origin,
    require_any_role,
    require_csrf,
    require_role,
)
from app.db.models import RoleName, ShipmentStatus, User
from app.db.session import get_db
from app.modules.shipments.schemas import (
    ShipmentCreate,
    ShipmentListResponse,
    ShipmentResponse,
    ShipmentUpdate,
)
from app.modules.shipments.service import (
    create_shipment,
    get_shipment,
    list_shipments,
    update_shipment,
)


router = APIRouter(prefix="/shipments", tags=["shipments"])
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


def _response(shipment) -> ShipmentResponse:
    return ShipmentResponse.model_validate(shipment)


@router.post(
    "",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_allowed_origin), Depends(require_csrf)],
)
def create(
    payload: ShipmentCreate,
    session: Annotated[Session, Depends(get_db)],
    user: ExecutiveUser,
) -> ShipmentResponse:
    shipment = create_shipment(session, payload, user)
    session.commit()
    session.refresh(shipment)
    return _response(shipment)


@router.get("", response_model=ShipmentListResponse)
def list_all(
    session: Annotated[Session, Depends(get_db)],
    user: ShipmentUser,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    shipment_status: ShipmentStatus | None = Query(default=None, alias="status"),
) -> ShipmentListResponse:
    shipments, total = list_shipments(
        session,
        user,
        limit=limit,
        offset=offset,
        status=shipment_status,
    )
    return ShipmentListResponse(
        items=[_response(shipment) for shipment in shipments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_one(
    shipment_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    user: ShipmentUser,
) -> ShipmentResponse:
    return _response(get_shipment(session, user, shipment_id))


@router.patch(
    "/{shipment_id}",
    response_model=ShipmentResponse,
    dependencies=[Depends(require_allowed_origin), Depends(require_csrf)],
)
def update(
    shipment_id: UUID,
    payload: ShipmentUpdate,
    session: Annotated[Session, Depends(get_db)],
    user: ExecutiveUser,
) -> ShipmentResponse:
    shipment = update_shipment(session, user, shipment_id, payload)
    session.commit()
    session.refresh(shipment)
    return _response(shipment)
