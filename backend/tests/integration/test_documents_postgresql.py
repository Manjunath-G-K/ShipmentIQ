"""Document upload and authorization integration tests against PostgreSQL."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import Role, RoleName, Shipment, ShipmentDocument, User
from app.db.session import get_session_factory
from app.main import app
from app.modules.documents.storage import PrivateFileStorage


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="set RUN_DB_INTEGRATION=1 to run PostgreSQL integration checks",
)


ORIGIN = "http://testserver"
EXECUTIVE_PASSWORD = "Document-Executive-123"
OTHER_EXECUTIVE_PASSWORD = "Other-Document-Executive-123"
MANAGER_PASSWORD = "Document-Manager-123"
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


@pytest.fixture(scope="module")
def document_users():
    suffix = uuid4()
    credentials = {
        "executive_email": f"document-executive-{suffix}@example.test",
        "other_executive_email": f"document-other-executive-{suffix}@example.test",
        "manager_email": f"document-manager-{suffix}@example.test",
    }
    session = get_session_factory()()
    users: list[User] = []
    try:
        roles = {
            role.name: role
            for role in session.scalars(
                select(Role).where(
                    Role.name.in_([role.value for role in RoleName])
                )
            )
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
            shipment_ids = select(Shipment.id).where(Shipment.created_by_id.in_(user_ids))
            documents = cleanup.scalars(
                select(ShipmentDocument).where(ShipmentDocument.shipment_id.in_(shipment_ids))
            ).all()
            storage = PrivateFileStorage(
                get_settings().document_storage_path,
                get_settings().document_max_size_bytes,
            )
            for document in documents:
                storage.delete(document.storage_key)
            cleanup.execute(delete(ShipmentDocument).where(ShipmentDocument.shipment_id.in_(shipment_ids)))
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


def create_shipment(client: TestClient) -> str:
    response = client.post(
        "/api/v1/shipments",
        json={
            "shipment_reference": f"SHP-{uuid4().hex[:10]}",
            "importer": "Synthetic Importer Pvt Ltd",
            "supplier": "Synthetic Supplier GmbH",
            "origin_country": "Germany",
            "description": "Synthetic document integration test",
        },
        headers=protected_write_headers(client),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_upload_list_download_duplicate_and_invalid_content(document_users) -> None:
    client = TestClient(app)
    assert login(client, document_users["executive_email"], EXECUTIVE_PASSWORD).status_code == 200
    shipment_id = create_shipment(client)
    headers = protected_write_headers(client)

    uploaded = client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "INVOICE"},
        files={"file": ("invoice.pdf", PDF, "application/pdf")},
        headers=headers,
    )
    assert uploaded.status_code == 201
    body = uploaded.json()
    assert body["document_type"] == "INVOICE"
    assert body["original_filename"] == "invoice.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["sha256"]

    listed = client.get(f"/api/v1/shipments/{shipment_id}/documents")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    downloaded = client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{body['id']}/download"
    )
    assert downloaded.status_code == 200
    assert downloaded.content == PDF
    assert "invoice.pdf" in downloaded.headers["content-disposition"]

    session = get_session_factory()()
    try:
        document = session.get(ShipmentDocument, UUID(body["id"]))
        assert document is not None
        storage = PrivateFileStorage(
            get_settings().document_storage_path,
            get_settings().document_max_size_bytes,
        )
        storage.delete(document.storage_key)
    finally:
        session.close()
    missing_file = client.get(
        f"/api/v1/shipments/{shipment_id}/documents/{body['id']}/download"
    )
    assert missing_file.status_code == 503
    assert missing_file.json()["error"]["code"] == "DOCUMENT_STORAGE_UNAVAILABLE"

    missing_upload = client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "PACKING_LIST"},
        headers=protected_write_headers(client),
    )
    assert missing_upload.status_code == 422
    assert missing_upload.json()["error"]["code"] == "VALIDATION_ERROR"

    duplicate = client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "INVOICE"},
        files={"file": ("other.pdf", PDF, "application/pdf")},
        headers=headers,
    )
    invalid = client.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "PACKING_LIST"},
        files={"file": ("packing.pdf", b"not-pdf", "application/pdf")},
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_DOCUMENT"


def test_document_access_is_scoped_and_writes_require_csrf(document_users) -> None:
    executive = TestClient(app)
    other_executive = TestClient(app)
    manager = TestClient(app)
    assert login(executive, document_users["executive_email"], EXECUTIVE_PASSWORD).status_code == 200
    assert login(
        other_executive,
        document_users["other_executive_email"],
        OTHER_EXECUTIVE_PASSWORD,
    ).status_code == 200
    assert login(manager, document_users["manager_email"], MANAGER_PASSWORD).status_code == 200

    shipment_id = create_shipment(executive)
    upload_response = executive.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "BILL_OF_LADING"},
        files={"file": ("bol.pdf", PDF, "application/pdf")},
        headers=protected_write_headers(executive),
    )
    document_id = upload_response.json()["id"]

    assert other_executive.get(f"/api/v1/shipments/{shipment_id}/documents").status_code == 404
    assert other_executive.get(
        f"/api/v1/shipments/{shipment_id}/documents/{document_id}/download"
    ).status_code == 404
    assert manager.get(f"/api/v1/shipments/{shipment_id}/documents").status_code == 200
    assert manager.get(
        f"/api/v1/shipments/{shipment_id}/documents/{document_id}/download"
    ).status_code == 200

    manager_upload = manager.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "PACKING_LIST"},
        files={"file": ("packing.pdf", PDF, "application/pdf")},
        headers=protected_write_headers(manager),
    )
    missing_csrf = executive.post(
        f"/api/v1/shipments/{shipment_id}/documents",
        data={"document_type": "PACKING_LIST"},
        files={"file": ("packing.pdf", PDF, "application/pdf")},
        headers={"Origin": ORIGIN},
    )
    assert manager_upload.status_code == 403
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "CSRF_FAILED"


def test_concurrent_duplicate_uploads_are_serialized_by_database(document_users) -> None:
    setup_client = TestClient(app)
    assert login(
        setup_client, document_users["executive_email"], EXECUTIVE_PASSWORD
    ).status_code == 200
    shipment_id = create_shipment(setup_client)
    storage = PrivateFileStorage(
        get_settings().document_storage_path,
        get_settings().document_max_size_bytes,
    )
    files_before = {path.name for path in storage.base_path.glob("*") if path.is_file()}

    def upload_once() -> int:
        client = TestClient(app)
        assert login(
            client, document_users["executive_email"], EXECUTIVE_PASSWORD
        ).status_code == 200
        response = client.post(
            f"/api/v1/shipments/{shipment_id}/documents",
            data={"document_type": "INVOICE"},
            files={"file": ("invoice.pdf", PDF, "application/pdf")},
            headers=protected_write_headers(client),
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: upload_once(), range(2)))

    assert sorted(statuses) == [201, 409]
    listed = setup_client.get(f"/api/v1/shipments/{shipment_id}/documents")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1
    files_after = {path.name for path in storage.base_path.glob("*") if path.is_file()}
    assert len(files_after - files_before) == 1
