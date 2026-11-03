"""Unit tests for authentication security primitives."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.security import hash_password, validate_password, verify_password
from app.main import app
from app.modules.auth.service import seed_demo_users


def test_passwords_use_argon2id_and_verify() -> None:
    password = "Correct-Horse-Battery-Staple"

    password_hash = hash_password(password)

    assert password_hash.startswith("$argon2id$")
    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("wrong-password", password_hash)


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_password_length_is_validated(password: str) -> None:
    with pytest.raises(ValueError, match="Password must be"):
        validate_password(password)


def test_invalid_password_hash_fails_closed() -> None:
    assert not verify_password("Correct-Horse-Battery-Staple", "not-a-hash")


def test_demo_user_seeding_is_blocked_in_production() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/shipmentiq",
        JWT_SECRET_KEY="test-only-secret-not-for-production",
        ENVIRONMENT="production",
        AUTH_COOKIE_SECURE=True,
        SEED_DEMO_USERS=True,
    )

    with pytest.raises(ValueError, match="disabled in production"):
        seed_demo_users(object(), settings)


def test_rbac_probe_routes_are_disabled_in_production() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/shipmentiq",
        JWT_SECRET_KEY="test-only-secret-not-for-production",
        ENVIRONMENT="production",
        AUTH_COOKIE_SECURE=True,
        AUTH_ALLOWED_ORIGINS="http://testserver",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = TestClient(app).get("/api/v1/auth/rbac/executive")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
