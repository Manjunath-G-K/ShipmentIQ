"""Transactional shipment queries and object-scope enforcement."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ShipmentNotFoundError
from app.db.models import RoleName, Shipment, ShipmentStatus, User
from app.modules.shipments.schemas import ShipmentCreate, ShipmentUpdate


def is_manager(user: User) -> bool:
    return RoleName.DOCUMENTATION_MANAGER.value in {role.name for role in user.roles}


def _scope_statement(user: User):
    statement = select(Shipment)
    if not is_manager(user):
        statement = statement.where(Shipment.created_by_id == user.id)
    return statement


def create_shipment(
    session: Session, payload: ShipmentCreate, created_by: User
) -> Shipment:
    shipment = Shipment(
        created_by_id=created_by.id,
        shipment_reference=payload.shipment_reference,
        importer=payload.importer,
        supplier=payload.supplier,
        origin_country=payload.origin_country,
        description=payload.description,
        status=ShipmentStatus.DRAFT.value,
    )
    session.add(shipment)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("Shipment reference already exists") from exc
    return shipment


def list_shipments(
    session: Session,
    user: User,
    *,
    limit: int,
    offset: int,
    status: ShipmentStatus | None = None,
) -> tuple[list[Shipment], int]:
    scoped = _scope_statement(user)
    if status is not None:
        scoped = scoped.where(Shipment.status == status.value)

    total = session.scalar(
        select(func.count()).select_from(scoped.order_by(None).subquery())
    ) or 0
    shipments = session.scalars(
        scoped.order_by(Shipment.updated_at.desc(), Shipment.id).limit(limit).offset(offset)
    ).all()
    return shipments, total


def get_shipment(session: Session, user: User, shipment_id: UUID) -> Shipment:
    shipment = session.scalar(_scope_statement(user).where(Shipment.id == shipment_id))
    if shipment is None:
        raise ShipmentNotFoundError()
    return shipment


def update_shipment(
    session: Session,
    user: User,
    shipment_id: UUID,
    payload: ShipmentUpdate,
) -> Shipment:
    shipment = session.scalar(
        _scope_statement(user).where(Shipment.id == shipment_id).with_for_update()
    )
    if shipment is None:
        raise ShipmentNotFoundError()

    for field_name in payload.model_fields_set:
        setattr(shipment, field_name, getattr(payload, field_name))
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("Shipment reference already exists") from exc
    return shipment
