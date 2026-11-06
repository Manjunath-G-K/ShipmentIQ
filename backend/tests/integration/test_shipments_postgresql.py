"""Shipment management API integration tests against PostgreSQL."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import Role, RoleName, Shipment, User
from app.db.session import get_session_factory
from app.main import app


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="set RUN_DB_INTEGRATION=1 to run PostgreSQL integration checks",
)


ORIGIN = "http://testserver"
EXECUTIVE_PASSWORD = "Executive-Password-123"
OTHER_EXECUTIVE_PASSWORD = "Other-Executive-Password-123"
MANAGER_PASSWORD = "Manager-Password-123"


@pytest.fixture(scope="module")
def shipment_users():
    suffix = uuid4()
    credentials = {
        "executive_email": f"shipment-executive-{suffix}@example.test",
        "other_executive_email": f"shipment-other-executive-{suffix}@example.test",
        "manager_email": f"shipment-manager-{suffix}@example.test",
    }
    session = get_session_factory()()
    users: list[User] = []
    try:
        roles = {
            role.name: role
            for role in session.scalars(
                select(Role).where(
                    Role.name.in_(
                        [
                            RoleName.DOCUMENTATION_EXECUTIVE.value,
                            RoleName.DOCUMENTATION_MANAGER.value,
                        ]
                    )
                )
            )
        }
        assert set(roles) == {
            RoleName.DOCUMENTATION_EXECUTIVE.value,
            RoleName.DOCUMENTATION_MANAGER.value,
        }
        executive = User(
            email=credentials["executive_email"],
            password_hash=hash_password(EXECUTIVE_PASSWORD),
        )
        other_executive = User(
            email=credentials["other_executive_email"],
            password_hash=hash_password(OTHER_EXECUTIVE_PASSWORD),
        )
        manager = User(
            email=credentials["manager_email"],
            password_hash=hash_password(MANAGER_PASSWORD),
        )
        executive.roles.append(roles[RoleName.DOCUMENTATION_EXECUTIVE.value])
        other_executive.roles.append(roles[RoleName.DOCUMENTATION_EXECUTIVE.value])
        manager.roles.append(roles[RoleName.DOCUMENTATION_MANAGER.value])
        users.extend([executive, other_executive, manager])
        session.add_all(users)
        session.commit()
        credentials.update(
            {
                "executive_id": executive.id,
                "other_executive_id": other_executive.id,
                "manager_id": manager.id,
            }
        )
        yield credentials
    finally:
        session.close()
        cleanup = get_session_factory()()
        try:
            user_ids = [user.id for user in users]
            cleanup.execute(delete(Shipment).where(Shipment.created_by_id.in_(user_ids)))
            cleanup.execute(delete(User).where(User.id.in_(user_ids)))
            cleanup.commit()
        finally:
            cleanup.close()


def login(client: TestClient, email: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": ORIGIN},
    )


def protected_write_headers(client: TestClient) -> dict[str, str]:
    csrf_token = client.cookies.get(get_settings().auth_csrf_cookie_name)
    return {"Origin": ORIGIN, "X-CSRF-Token": csrf_token}


def csrf_bootstrap_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf", headers={"Origin": ORIGIN})
    assert response.status_code == 200
    token = response.json()["csrf_token"]
    assert token == client.cookies.get(get_settings().auth_csrf_cookie_name)
    return {"Origin": ORIGIN, "X-CSRF-Token": token}


def payload(reference: str) -> dict[str, str]:
    return {
        "shipment_reference": reference,
        "importer": "Example Importer Pvt Ltd",
        "supplier": "Example Supplier GmbH",
        "origin_country": "Germany",
        "description": "Synthetic shipment for integration testing",
    }


def test_create_get_and_update_shipment(shipment_users) -> None:
    client = TestClient(app)
    assert login(
        client, shipment_users["executive_email"], EXECUTIVE_PASSWORD
    ).status_code == 200

    created = client.post(
        "/api/v1/shipments",
        json=payload(f"SHP-{uuid4().hex[:10]}"),
        headers=csrf_bootstrap_headers(client),
    )

    assert created.status_code == 201
    body = created.json()
    shipment_id = body["id"]
    assert body["status"] == "DRAFT"
    assert "created_by_id" not in body
    assert body["importer"] == "Example Importer Pvt Ltd"

    fetched = client.get(f"/api/v1/shipments/{shipment_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == shipment_id

    updated = client.patch(
        f"/api/v1/shipments/{shipment_id}",
        json={"description": "Updated synthetic description"},
        headers=protected_write_headers(client),
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated synthetic description"
    assert updated.json()["status"] == "DRAFT"


def test_duplicate_reference_and_mass_assignment_are_rejected(shipment_users) -> None:
    client = TestClient(app)
    assert login(
        client, shipment_users["executive_email"], EXECUTIVE_PASSWORD
    ).status_code == 200
    reference = f"SHP-{uuid4().hex[:10]}"
    headers = protected_write_headers(client)

    first = client.post("/api/v1/shipments", json=payload(reference), headers=headers)
    duplicate = client.post("/api/v1/shipments", json=payload(reference.lower()), headers=headers)
    status_write = client.post(
        "/api/v1/shipments",
        json={**payload(f"SHP-{uuid4().hex[:10]}"), "status": "EXPORTED"},
        headers=headers,
    )
    owner_write = client.post(
        "/api/v1/shipments",
        json={**payload(f"SHP-{uuid4().hex[:10]}"), "created_by_id": str(uuid4())},
        headers=headers,
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"
    assert status_write.status_code == 422
    assert owner_write.status_code == 422


def test_list_pagination_and_status_filter(shipment_users) -> None:
    client = TestClient(app)
    assert login(
        client, shipment_users["executive_email"], EXECUTIVE_PASSWORD
    ).status_code == 200
    references = [f"SHP-{uuid4().hex[:10]}" for _ in range(3)]
    headers = protected_write_headers(client)
    for reference in references:
        assert client.post("/api/v1/shipments", json=payload(reference), headers=headers).status_code == 201

    page = client.get("/api/v1/shipments?limit=2&offset=1")
    filtered = client.get("/api/v1/shipments?status=DRAFT&limit=100")

    assert page.status_code == 200
    assert page.json()["limit"] == 2
    assert page.json()["offset"] == 1
    assert len(page.json()["items"]) <= 2
    assert page.json()["total"] >= 3
    assert {item["status"] for item in filtered.json()["items"]} == {"DRAFT"}

    assert client.get("/api/v1/shipments?limit=101").status_code == 422
    assert client.get("/api/v1/shipments?offset=-1").status_code == 422
    assert client.get("/api/v1/shipments?status=UNKNOWN").status_code == 422


def test_object_scope_and_role_permissions(shipment_users) -> None:
    executive = TestClient(app)
    other_executive = TestClient(app)
    manager = TestClient(app)
    assert login(
        executive, shipment_users["executive_email"], EXECUTIVE_PASSWORD
    ).status_code == 200
    assert login(
        other_executive,
        shipment_users["other_executive_email"],
        OTHER_EXECUTIVE_PASSWORD,
    ).status_code == 200
    assert login(manager, shipment_users["manager_email"], MANAGER_PASSWORD).status_code == 200

    created = executive.post(
        "/api/v1/shipments",
        json=payload(f"SHP-{uuid4().hex[:10]}"),
        headers=protected_write_headers(executive),
    )
    shipment_id = created.json()["id"]

    assert other_executive.get(f"/api/v1/shipments/{shipment_id}").status_code == 404
    assert manager.get(f"/api/v1/shipments/{shipment_id}").status_code == 200
    assert manager.get("/api/v1/shipments").status_code == 200
    assert other_executive.patch(
        f"/api/v1/shipments/{shipment_id}",
        json={"description": "unauthorized"},
        headers=protected_write_headers(other_executive),
    ).status_code == 404
    assert manager.patch(
        f"/api/v1/shipments/{shipment_id}",
        json={"description": "manager write"},
        headers=protected_write_headers(manager),
    ).status_code == 403
    assert manager.post(
        "/api/v1/shipments",
        json=payload(f"SHP-{uuid4().hex[:10]}"),
        headers=protected_write_headers(manager),
    ).status_code == 403


def test_state_changes_require_csrf_and_origin_and_status_is_immutable(shipment_users) -> None:
    client = TestClient(app)
    assert login(
        client, shipment_users["executive_email"], EXECUTIVE_PASSWORD
    ).status_code == 200
    missing_csrf_create = client.post(
        "/api/v1/shipments",
        json=payload(f"SHP-{uuid4().hex[:10]}"),
        headers={"Origin": ORIGIN},
    )
    created = client.post(
        "/api/v1/shipments",
        json=payload(f"SHP-{uuid4().hex[:10]}"),
        headers=protected_write_headers(client),
    )
    shipment_id = created.json()["id"]

    missing_csrf = client.patch(
        f"/api/v1/shipments/{shipment_id}",
        json={"description": "blocked"},
        headers={"Origin": ORIGIN},
    )
    invalid_origin = client.patch(
        f"/api/v1/shipments/{shipment_id}",
        json={"description": "blocked"},
        headers={**protected_write_headers(client), "Origin": "https://evil.example"},
    )
    status_write = client.patch(
        f"/api/v1/shipments/{shipment_id}",
        json={"status": "EXPORTED"},
        headers=protected_write_headers(client),
    )
    empty_update = client.patch(
        f"/api/v1/shipments/{shipment_id}",
        json={},
        headers=protected_write_headers(client),
    )

    assert missing_csrf_create.status_code == 403
    assert missing_csrf_create.json()["error"]["code"] == "CSRF_FAILED"
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "CSRF_FAILED"
    assert invalid_origin.status_code == 403
    assert invalid_origin.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"
    assert status_write.status_code == 422
    assert empty_update.status_code == 422
