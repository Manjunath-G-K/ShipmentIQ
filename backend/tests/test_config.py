"""Configuration validation tests."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_load_postgresql_configuration(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:password@localhost:5432/shipmentiq",
    )
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "7")

    settings = Settings(_env_file=None)

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.db_connect_timeout == 7


def test_settings_reject_sqlite(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./not-allowed.db")

    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(_env_file=None)


def test_settings_reject_non_positive_timeout(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:password@localhost:5432/shipmentiq",
    )
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "0")

    with pytest.raises(ValidationError, match="DB_CONNECT_TIMEOUT"):
        Settings(_env_file=None)


def test_production_requires_secure_auth_cookie(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost:5432/shipmentiq")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-secret-not-for-production")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")

    with pytest.raises(ValidationError, match="AUTH_COOKIE_SECURE"):
        Settings(_env_file=None)


def test_document_storage_rejects_public_web_directory(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:password@localhost:5432/shipmentiq",
    )
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", "static/documents")

    with pytest.raises(ValidationError, match="public web directory"):
        Settings(_env_file=None)
