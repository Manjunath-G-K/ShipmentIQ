"""Opt-in checks against a real PostgreSQL instance."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.db.engine import get_engine
from app.main import app


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="set RUN_DB_INTEGRATION=1 to run PostgreSQL integration checks",
)


def test_migrations_created_schema() -> None:
    """The Alembic head is installed in the configured PostgreSQL database."""

    with get_engine().connect() as connection:
        table_name = connection.scalar(
            text("SELECT to_regclass('public.alembic_version')")
        )
        version = connection.scalar(text("SELECT version_num FROM alembic_version"))

    assert table_name == "alembic_version"
    assert version == "0004_shipment_documents"

    with get_engine().connect() as connection:
        tables = {
            connection.scalar(
                text("SELECT to_regclass(:table_name)"), {"table_name": table}
            )
            for table in (
                "public.users",
                "public.roles",
                "public.user_roles",
                "public.shipments",
                "public.shipment_documents",
            )
        }

    assert tables == {"users", "roles", "user_roles", "shipments", "shipment_documents"}


def test_sqlalchemy_insert_and_retrieve_is_rollback_safe() -> None:
    """SQLAlchemy can round-trip a record without leaving test data behind."""

    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(
                text(
                    "CREATE TEMPORARY TABLE shipmentiq_integration_record "
                    "(id integer PRIMARY KEY, value text NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO shipmentiq_integration_record (id, value) "
                    "VALUES (:id, :value)"
                ),
                {"id": 1, "value": "rollback-safe"},
            )
            record = connection.execute(
                text(
                    "SELECT id, value FROM shipmentiq_integration_record "
                    "WHERE id = :id"
                ),
                {"id": 1},
            ).one()
            assert tuple(record) == (1, "rollback-safe")
        finally:
            transaction.rollback()

        assert connection.scalar(
            text(
                "SELECT to_regclass('pg_temp.shipmentiq_integration_record')"
            )
        ) is None


def test_readiness_endpoint_returns_200_with_postgresql() -> None:
    """FastAPI readiness uses the reachable PostgreSQL database."""

    response = TestClient(app).get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_readiness_endpoint_returns_503_for_unreachable_postgresql(monkeypatch) -> None:
    """A real SQLAlchemy connection failure becomes the safe readiness response."""

    from app.core import database_check

    unavailable_engine = create_engine(
        "postgresql+psycopg://shipmentiq_dev:change-me-locally@127.0.0.1:59999/shipmentiq",
        connect_args={"connect_timeout": 1},
    )
    monkeypatch.setattr(database_check, "get_engine", lambda: unavailable_engine)

    try:
        response = TestClient(app).get("/api/v1/health/ready")
    finally:
        unavailable_engine.dispose()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert response.json()["error"]["message"] == "Database readiness check failed"
