"""Reusable authentication, authorization, CSRF, and origin dependencies."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.errors import (
    AuthenticationError,
    AuthorizationError,
    CSRFError,
    DevelopmentOnlyEndpointError,
    OriginNotAllowedError,
)
from app.core.security import csrf_tokens_match, decode_access_token
from app.db.models import RoleName, User
from app.db.session import get_db


def require_allowed_origin(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    """Require an explicit allowed Origin for state-changing auth requests."""

    origin = request.headers.get("origin")
    if origin is None or origin not in settings.allowed_origins():
        raise OriginNotAllowedError()


def require_rbac_probe_enabled(
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Keep milestone-only RBAC probe routes out of production deployments."""

    if settings.environment.lower() == "production":
        raise DevelopmentOnlyEndpointError()


def require_csrf(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    """Validate the double-submit CSRF cookie/header pair."""

    cookie_token = request.cookies.get(settings.auth_csrf_cookie_name)
    header_token = request.headers.get(settings.auth_csrf_header_name)
    session_token = request.cookies.get(settings.auth_cookie_name)
    if not csrf_tokens_match(cookie_token, header_token, session_token, settings):
        raise CSRFError()


def get_current_user(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Authenticate from the HttpOnly cookie and reload roles from PostgreSQL."""

    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise AuthenticationError()

    try:
        user_id: UUID = decode_access_token(token, settings)
    except (RuntimeError, ValueError):
        raise AuthenticationError() from None

    user = session.scalar(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )
    if user is None or not user.is_active:
        raise AuthenticationError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(required_role: RoleName) -> Callable:
    """Build a dependency that checks a role loaded from the database."""

    def dependency(user: CurrentUser) -> User:
        if required_role.value not in {role.name for role in user.roles}:
            raise AuthorizationError()
        return user

    return dependency


def require_any_role(*required_roles: RoleName) -> Callable:
    """Build a dependency that accepts any one of the supplied roles."""

    allowed = {role.value for role in required_roles}

    def dependency(user: CurrentUser) -> User:
        if not allowed.intersection(role.name for role in user.roles):
            raise AuthorizationError()
        return user

    return dependency
