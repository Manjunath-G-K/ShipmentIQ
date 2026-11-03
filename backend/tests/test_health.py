"""API health and readiness tests."""

from fastapi.testclient import TestClient

from app.api.routes import health as health_routes
from app.core.errors import DatabaseUnavailableError
from app.main import app

client = TestClient(app)


def test_health_endpoint_is_live() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_reports_database_ready(monkeypatch) -> None:
    monkeypatch.setattr(health_routes, "check_database_connection", lambda: None)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_readiness_endpoint_reports_database_unavailable(monkeypatch) -> None:
    def unavailable() -> None:
        raise DatabaseUnavailableError()

    monkeypatch.setattr(health_routes, "check_database_connection", unavailable)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert response.json()["error"]["message"] == "Database readiness check failed"
    assert response.headers["x-request-id"]
