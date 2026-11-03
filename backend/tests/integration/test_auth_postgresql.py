"""Authentication and RBAC integration tests against PostgreSQL."""

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.engine import get_engine
from app.db.models import Role, RoleName, User
from app.db.session import get_session_factory
from app.main import app
from app.modules.auth.service import seed_demo_users


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="set RUN_DB_INTEGRATION=1 to run PostgreSQL integration checks",
)


ORIGIN = "http://testserver"
EXECUTIVE_PASSWORD = "Executive-Password-123"
MANAGER_PASSWORD = "Manager-Password-123"


@pytest.fixture(scope="module")
def auth_users():
    executive_email = f"executive-{uuid4()}@example.test"
    manager_email = f"manager-{uuid4()}@example.test"
    session = get_session_factory()()
    try:
        executive_role = session.scalar(
            select(Role).where(Role.name == RoleName.DOCUMENTATION_EXECUTIVE.value)
        )
        manager_role = session.scalar(
            select(Role).where(Role.name == RoleName.DOCUMENTATION_MANAGER.value)
        )
        assert executive_role is not None
        assert manager_role is not None

        executive = User(
            email=executive_email,
            password_hash=hash_password(EXECUTIVE_PASSWORD),
            is_active=True,
        )
        manager = User(
            email=manager_email,
            password_hash=hash_password(MANAGER_PASSWORD),
            is_active=True,
        )
        executive.roles.append(executive_role)
        manager.roles.append(manager_role)
        session.add_all([executive, manager])
        session.commit()
        yield {
            "executive_email": executive_email,
            "manager_email": manager_email,
            "executive_id": executive.id,
            "manager_id": manager.id,
        }
    finally:
        if "executive" in locals():
            session.delete(executive)
        if "manager" in locals():
            session.delete(manager)
        session.commit()
        session.close()


def login(client: TestClient, email: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": ORIGIN},
    )


def test_login_sets_cookie_session_and_me(auth_users) -> None:
    client = TestClient(app)

    response = login(client, auth_users["executive_email"], EXECUTIVE_PASSWORD)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == auth_users["executive_email"]
    assert body["roles"] == [RoleName.DOCUMENTATION_EXECUTIVE.value]
    assert "password_hash" not in body
    set_cookie_headers = response.headers.get_list("set-cookie")
    session_cookie = next(value for value in set_cookie_headers if "shipmentiq_session=" in value)
    csrf_cookie = next(value for value in set_cookie_headers if "shipmentiq_csrf=" in value)
    assert "HttpOnly" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "SameSite=lax" in session_cookie

    me_response = client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    assert me_response.json() == body


def test_invalid_credentials_and_invalid_input_are_rejected(auth_users) -> None:
    client = TestClient(app)

    invalid = login(client, auth_users["executive_email"], "Wrong-Password-123")
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert "shipmentiq_session" not in client.cookies

    invalid_input = client.post(
        "/api/v1/auth/login",
        json={"email": auth_users["executive_email"], "password": "short"},
        headers={"Origin": ORIGIN},
    )
    assert invalid_input.status_code == 422
    assert '"input":"short"' not in invalid_input.text


@pytest.mark.parametrize("token_value", ["not-a-jwt", "expired"])
def test_invalid_or_expired_jwt_is_rejected(auth_users, token_value: str) -> None:
    client = TestClient(app)
    settings = get_settings()
    if token_value == "expired":
        token_value = jwt.encode(
            {
                "sub": str(auth_users["executive_id"]),
                "iss": settings.jwt_issuer,
                "aud": settings.jwt_audience,
                "iat": datetime.now(timezone.utc) - timedelta(hours=2),
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
                "jti": str(uuid4()),
                "token_type": "access",
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
    client.cookies.set(settings.auth_cookie_name, token_value)

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_logout_requires_origin_and_csrf_then_clears_session(auth_users) -> None:
    client = TestClient(app)
    login_response = login(client, auth_users["executive_email"], EXECUTIVE_PASSWORD)
    assert login_response.status_code == 200
    csrf_token = client.cookies.get(get_settings().auth_csrf_cookie_name)

    missing_csrf = client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN})
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "CSRF_FAILED"

    invalid_origin = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "https://evil.example", "X-CSRF-Token": csrf_token},
    )
    assert invalid_origin.status_code == 403
    assert invalid_origin.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"

    logout_response = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
    )
    assert logout_response.status_code == 200
    assert logout_response.json() == {"status": "logged_out"}
    assert client.get("/api/v1/auth/me").status_code == 401


def test_csrf_cookie_injection_is_rejected(auth_users) -> None:
    client = TestClient(app)
    assert login(client, auth_users["executive_email"], EXECUTIVE_PASSWORD).status_code == 200
    settings = get_settings()
    attacker_token = "attacker-controlled-cookie-value"
    client.cookies.set(settings.auth_csrf_cookie_name, attacker_token)

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": attacker_token},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


def test_login_rejects_untrusted_origin(auth_users) -> None:
    response = TestClient(app).post(
        "/api/v1/auth/login",
        json={"email": auth_users["executive_email"], "password": EXECUTIVE_PASSWORD},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"


def test_unauthenticated_and_role_protected_routes(auth_users) -> None:
    anonymous = TestClient(app)
    assert anonymous.get("/api/v1/auth/me").status_code == 401
    assert anonymous.get("/api/v1/auth/rbac/executive").status_code == 401

    executive = TestClient(app)
    assert login(executive, auth_users["executive_email"], EXECUTIVE_PASSWORD).status_code == 200
    assert executive.get("/api/v1/auth/rbac/executive").status_code == 200
    manager_denied = executive.get("/api/v1/auth/rbac/manager")
    assert manager_denied.status_code == 403
    assert manager_denied.json()["error"]["code"] == "FORBIDDEN"

    manager = TestClient(app)
    assert login(manager, auth_users["manager_email"], MANAGER_PASSWORD).status_code == 200
    assert manager.get("/api/v1/auth/rbac/manager").status_code == 200
    executive_denied = manager.get("/api/v1/auth/rbac/executive")
    assert executive_denied.status_code == 403


def test_jwt_role_claims_do_not_override_database_roles(auth_users) -> None:
    client = TestClient(app)
    settings = get_settings()
    forged_role_claim_token = jwt.encode(
        {
            "sub": str(auth_users["executive_id"]),
            "roles": [RoleName.DOCUMENTATION_MANAGER.value],
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "jti": str(uuid4()),
            "token_type": "access",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    client.cookies.set(settings.auth_cookie_name, forged_role_claim_token)

    response = client.get("/api/v1/auth/rbac/manager")

    assert response.status_code == 403


def test_demo_user_seeding_is_idempotent() -> None:
    suffix = uuid4()
    settings = Settings(
        _env_file=None,
        DATABASE_URL=os.environ["DATABASE_URL"],
        JWT_SECRET_KEY=os.environ["JWT_SECRET_KEY"],
        AUTH_ALLOWED_ORIGINS=ORIGIN,
        SEED_DEMO_USERS=True,
        DEMO_EXECUTIVE_EMAIL=f"seed-executive-{suffix}@example.test",
        DEMO_EXECUTIVE_PASSWORD="Seed-Executive-123",
        DEMO_MANAGER_EMAIL=f"seed-manager-{suffix}@example.test",
        DEMO_MANAGER_PASSWORD="Seed-Manager-123",
    )
    session = get_session_factory()()
    try:
        first = seed_demo_users(session, settings)
        first_ids = [user.id for user in first]
        second = seed_demo_users(session, settings)
        second_ids = [user.id for user in second]

        assert first_ids == second_ids
        assert len(
            session.scalars(
                select(User).where(
                    User.email.in_(
                        [
                            settings.demo_executive_email,
                            settings.demo_manager_email,
                        ]
                    )
                )
            ).all()
        ) == 2
    finally:
        session.rollback()
        session.close()
