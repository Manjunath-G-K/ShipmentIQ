"""Authentication and role-based access endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.dependencies import (
    CurrentUser,
    require_allowed_origin,
    require_csrf,
    require_rbac_probe_enabled,
    require_role,
)
from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationError
from app.core.security import create_access_token, new_csrf_token
from app.db.models import RoleName
from app.db.session import get_db
from app.modules.auth.schemas import (
    AccessResponse,
    LoginRequest,
    LogoutResponse,
    UserResponse,
)
from app.modules.auth.service import authenticate_user, user_roles


router = APIRouter(prefix="/auth", tags=["auth"])


def _user_response(user) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, roles=user_roles(user))


def _set_session_cookies(response: Response, token: str, csrf_token: str, settings: Settings) -> None:
    cookie_kwargs = {
        "path": "/",
        "secure": settings.auth_cookie_secure,
        "samesite": settings.auth_cookie_samesite,
        "max_age": settings.jwt_expire_minutes * 60,
    }
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        httponly=True,
        **cookie_kwargs,
    )
    response.set_cookie(
        settings.auth_csrf_cookie_name,
        csrf_token,
        httponly=False,
        **cookie_kwargs,
    )


def _clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.auth_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )
    response.delete_cookie(
        settings.auth_csrf_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=False,
        samesite=settings.auth_cookie_samesite,
    )


@router.post(
    "/login",
    response_model=UserResponse,
    dependencies=[Depends(require_allowed_origin)],
)
def login(
    payload: LoginRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserResponse:
    user = authenticate_user(session, payload.email, payload.password.get_secret_value())
    if user is None:
        raise AuthenticationError(invalid_credentials=True)

    token = create_access_token(user.id, settings)
    _set_session_cookies(response, token, new_csrf_token(token, settings), settings)
    return _user_response(user)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    dependencies=[Depends(require_allowed_origin), Depends(require_csrf)],
)
def logout(
    response: Response,
    _user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> LogoutResponse:
    _clear_session_cookies(response, settings)
    return LogoutResponse(status="logged_out")


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return _user_response(user)


@router.get(
    "/rbac/executive",
    response_model=AccessResponse,
    dependencies=[Depends(require_rbac_probe_enabled)],
)
def executive_access(
    _user: Annotated[
        object,
        Depends(require_role(RoleName.DOCUMENTATION_EXECUTIVE)),
    ],
) -> AccessResponse:
    return AccessResponse(access="granted", role=RoleName.DOCUMENTATION_EXECUTIVE.value)


@router.get(
    "/rbac/manager",
    response_model=AccessResponse,
    dependencies=[Depends(require_rbac_probe_enabled)],
)
def manager_access(
    _user: Annotated[
        object,
        Depends(require_role(RoleName.DOCUMENTATION_MANAGER)),
    ],
) -> AccessResponse:
    return AccessResponse(access="granted", role=RoleName.DOCUMENTATION_MANAGER.value)
