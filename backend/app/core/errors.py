"""Consistent application exception and HTTP error handling."""

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.schemas import ErrorBody, ErrorResponse


class APIError(Exception):
    """An expected application error safe to expose to an API client."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class DatabaseUnavailableError(APIError):
    """The readiness probe could not reach or query PostgreSQL."""

    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message="Database readiness check failed",
        )


class AuthenticationError(APIError):
    """The request has no valid authenticated user or credentials."""

    def __init__(self, *, invalid_credentials: bool = False) -> None:
        super().__init__(
            status_code=401,
            code="INVALID_CREDENTIALS" if invalid_credentials else "AUTHENTICATION_REQUIRED",
            message=(
                "Invalid email or password"
                if invalid_credentials
                else "Authentication required"
            ),
        )


class AuthorizationError(APIError):
    """The authenticated user lacks the required server-side role."""

    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            code="FORBIDDEN",
            message="You do not have permission to perform this action",
        )


class CSRFError(APIError):
    """A cookie-authenticated state-changing request failed CSRF validation."""

    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            code="CSRF_FAILED",
            message="CSRF validation failed",
        )


class OriginNotAllowedError(APIError):
    """A state-changing request came from an untrusted origin."""

    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            code="ORIGIN_NOT_ALLOWED",
            message="Request origin is not allowed",
        )


class DevelopmentOnlyEndpointError(APIError):
    """A development verification endpoint is not available in production."""

    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            code="NOT_FOUND",
            message="Resource not found",
        )


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid4()))


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=details,
            request_id=_request_id(request),
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    """Register safe, consistent handlers for expected API failures."""

    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        return _error_response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=422,
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details=exc.errors(),
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=503,
            code="DATABASE_ERROR",
            message="Database operation failed",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request, exc: Exception
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        )
