"""Human review, deterministic validation, and accuracy-report endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_allowed_origin, require_any_role, require_csrf, require_role
from app.core.config import Settings, get_settings
from app.db.models import RoleName, User
from app.db.session import get_db
from app.modules.review.schemas import (
    AccuracyReportResponse,
    FieldCorrectionRequest,
    ReviewDecisionRequest,
    ReviewFieldResponse,
    ReviewResponse,
    RevisionResponse,
    ValidationResponse,
    ValidationRunResponse,
)
from app.modules.review.service import (
    accuracy_report,
    confirm_field,
    correct_field,
    get_revisions,
    get_validations,
    reject_field,
    review_snapshot,
    run_validations,
)


router = APIRouter(tags=["review"])
ShipmentUser = Annotated[
    User,
    Depends(
        require_any_role(
            RoleName.DOCUMENTATION_EXECUTIVE, RoleName.DOCUMENTATION_MANAGER
        )
    ),
]
ExecutiveUser = Annotated[User, Depends(require_role(RoleName.DOCUMENTATION_EXECUTIVE))]
ManagerUser = Annotated[User, Depends(require_role(RoleName.DOCUMENTATION_MANAGER))]


@router.get("/shipments/{shipment_id}/review", response_model=ReviewResponse)
def read_review(
    shipment_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    user: ShipmentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReviewResponse:
    return ReviewResponse.model_validate(
        review_snapshot(session, user, shipment_id, settings.extraction_low_confidence_threshold)
    )


@router.post(
    "/shipments/{shipment_id}/validations/run",
    response_model=ValidationRunResponse,
    dependencies=[Depends(require_allowed_origin), Depends(require_csrf)],
)
def run_validation_checks(
    shipment_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    user: ShipmentUser,
) -> ValidationRunResponse:
    return ValidationRunResponse(
        shipment_id=shipment_id,
        validations=[ValidationResponse.model_validate(item) for item in run_validations(session, user, shipment_id)],
    )


@router.get("/shipments/{shipment_id}/validations", response_model=list[ValidationResponse])
def read_validation_checks(
    shipment_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    user: ShipmentUser,
) -> list[ValidationResponse]:
    return [ValidationResponse.model_validate(item) for item in get_validations(session, user, shipment_id)]


@router.patch(
    "/fields/{field_id}",
    response_model=ReviewFieldResponse,
    dependencies=[Depends(require_allowed_origin), Depends(require_csrf)],
)
def correct(
    field_id: UUID,
    payload: FieldCorrectionRequest,
    session: Annotated[Session, Depends(get_db)],
    user: ExecutiveUser,
) -> ReviewFieldResponse:
    field = correct_field(session, user, field_id, payload.value, payload.note, payload.expected_version)
    return ReviewFieldResponse(
        id=field.id,
        document_id=field.document_id,
        field_path=field.field_path,
        value_type=field.value_type,
        value=field.current_value,
        extracted_value=field.extracted_value,
        confidence=float(field.confidence) if field.confidence is not None else None,
        source_references=field.source_references,
        status=field.status,
        version=field.version,
        flags=["NEEDS_CONFIRMATION"],
        last_reviewed_by_id=field.last_reviewed_by_id,
        last_reviewed_at=field.last_reviewed_at,
    )


@router.post(
    "/fields/{field_id}/confirm",
    response_model=ReviewFieldResponse,
    dependencies=[Depends(require_allowed_origin), Depends(require_csrf)],
)
def confirm(
    field_id: UUID,
    payload: ReviewDecisionRequest,
    session: Annotated[Session, Depends(get_db)],
    user: ShipmentUser,
) -> ReviewFieldResponse:
    field = confirm_field(session, user, field_id, payload.note, payload.expected_version)
    return ReviewFieldResponse(
        id=field.id,
        document_id=field.document_id,
        field_path=field.field_path,
        value_type=field.value_type,
        value=field.current_value,
        extracted_value=field.extracted_value,
        confidence=float(field.confidence) if field.confidence is not None else None,
        source_references=field.source_references,
        status=field.status,
        version=field.version,
        flags=[],
        last_reviewed_by_id=field.last_reviewed_by_id,
        last_reviewed_at=field.last_reviewed_at,
    )


@router.post(
    "/fields/{field_id}/reject",
    response_model=ReviewFieldResponse,
    dependencies=[Depends(require_allowed_origin), Depends(require_csrf)],
)
def reject(
    field_id: UUID,
    payload: ReviewDecisionRequest,
    session: Annotated[Session, Depends(get_db)],
    user: ShipmentUser,
) -> ReviewFieldResponse:
    field = reject_field(session, user, field_id, payload.note, payload.expected_version)
    return ReviewFieldResponse(
        id=field.id,
        document_id=field.document_id,
        field_path=field.field_path,
        value_type=field.value_type,
        value=field.current_value,
        extracted_value=field.extracted_value,
        confidence=float(field.confidence) if field.confidence is not None else None,
        source_references=field.source_references,
        status=field.status,
        version=field.version,
        flags=["REJECTED", "MISSING"],
        last_reviewed_by_id=field.last_reviewed_by_id,
        last_reviewed_at=field.last_reviewed_at,
    )


@router.get("/fields/{field_id}/revisions", response_model=list[RevisionResponse])
def read_revisions(
    field_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    user: ShipmentUser,
) -> list[RevisionResponse]:
    return [RevisionResponse.model_validate(item) for item in get_revisions(session, user, field_id)]


@router.get(
    "/reports/accuracy",
    response_model=AccuracyReportResponse,
)
def read_accuracy_report(
    session: Annotated[Session, Depends(get_db)],
    user: ManagerUser,
) -> AccuracyReportResponse:
    fields, suppliers = accuracy_report(session, user)
    return AccuracyReportResponse(field_metrics=fields, supplier_metrics=suppliers)
