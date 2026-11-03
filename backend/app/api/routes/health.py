"""Health and database readiness endpoints."""

from fastapi import APIRouter

from app.core.database_check import check_database_connection
from app.core.errors import DatabaseUnavailableError
from app.core.schemas import HealthResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return a process-level liveness response without requiring PostgreSQL."""

    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
def readiness() -> ReadinessResponse:
    """Verify that the configured PostgreSQL database can execute a trivial query."""

    try:
        check_database_connection()
    except DatabaseUnavailableError:
        raise
    except Exception as exc:  # pragma: no cover - defensive boundary for readiness probes
        raise DatabaseUnavailableError() from exc

    return ReadinessResponse(status="ready", database="ok")
