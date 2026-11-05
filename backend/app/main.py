"""FastAPI application entry point for the ShipmentIQ backend foundation."""

from uuid import uuid4

from fastapi import FastAPI, Request
from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.extraction import router as extraction_router
from app.api.routes.exports import router as exports_router
from app.api.routes.review import router as review_router
from app.api.routes.health import router as health_router
from app.api.routes.shipments import router as shipments_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers


def create_app() -> FastAPI:
    """Construct the application without connecting to PostgreSQL at import time."""

    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="ShipmentIQ backend",
    )
    @application.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID", str(uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    application.include_router(health_router, prefix=settings.api_v1_prefix)
    application.include_router(auth_router, prefix=settings.api_v1_prefix)
    application.include_router(shipments_router, prefix=settings.api_v1_prefix)
    application.include_router(documents_router, prefix=settings.api_v1_prefix)
    application.include_router(extraction_router, prefix=settings.api_v1_prefix)
    application.include_router(exports_router, prefix=settings.api_v1_prefix)
    application.include_router(review_router, prefix=settings.api_v1_prefix)
    register_exception_handlers(application)
    return application


app = create_app()
