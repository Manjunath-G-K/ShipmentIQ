"""Document upload and authorization integration tests against PostgreSQL."""

import os
import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from io import StringIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import DocumentExtraction, ReviewField, Role, RoleName, Shipment, ShipmentDocument, ShipmentValidation, User
from app.db.session import get_session_factory
from app.main import app
from app.modules.documents.storage import PrivateFileStorage
from app.modules.extraction.api import get_ai_provider, get_ocr_provider
from app.modules.extraction.providers import AIProviderError
from app.modules.extraction.schemas import (
    ExtractionResult,
    ExtractedDecimal,
    ExtractedDate,
    ExtractedInteger,
    ExtractedString,
    InvoiceFields,
    LineItem,
    OCRPage,
    PartyFields,
    ShipmentFields,
)


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
            cleanup.execute(
                delete(ShipmentValidation).where(
                    ShipmentValidation.shipment_id.in_(shipment_ids)
                )
            )
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


def test_extraction_result_and_status_are_persisted(document_users) -> None:
    class FakeOCR:
        name = "fake-ocr"

        def extract(self, content: bytes, content_type: str):
            return [OCRPage(page=1, text="synthetic", readable=True, source="embedded_text")]

    class FakeAI:
        name = "fake-ai"

        def extract(self, pages, document_type):
            return ExtractionResult(
                document_type=document_type,
                pages=pages,
                parties=PartyFields(
                    importer=ExtractedString(value="Synthetic Importer", confidence=0.95, sources=[{"page": 1, "locator": "label:importer"}]),
                    supplier=ExtractedString(value="Synthetic Supplier", confidence=0.95, sources=[{"page": 1, "locator": "label:supplier"}]),
                ),
            )

    app.dependency_overrides[get_ocr_provider] = lambda: FakeOCR()
    app.dependency_overrides[get_ai_provider] = lambda: FakeAI()
    try:
        client = TestClient(app)
        assert login(client, document_users["executive_email"], EXECUTIVE_PASSWORD).status_code == 200
        shipment_id = create_shipment(client)
        upload = client.post(
            f"/api/v1/shipments/{shipment_id}/documents",
            data={"document_type": "INVOICE"},
            files={"file": ("invoice.pdf", PDF, "application/pdf")},
            headers=protected_write_headers(client),
        )
        assert upload.status_code == 201
        document_id = upload.json()["id"]

        extracted = client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{document_id}/extract",
            headers=protected_write_headers(client),
        )
        assert extracted.status_code == 200
        assert extracted.json()["status"] == "NEEDS_REVIEW"
        assert extracted.json()["result"]["pages"][0]["page"] == 1
        assert extracted.json()["result"]["parties"]["supplier"]["sources"][0]["page"] == 1

        session = get_session_factory()()
        try:
            persisted = session.scalar(select(DocumentExtraction).where(DocumentExtraction.document_id == UUID(document_id)))
            assert persisted is not None
            assert persisted.status == "NEEDS_REVIEW"
            assert persisted.result["parties"]["supplier"]["value"] == "Synthetic Supplier"
        finally:
            session.close()
    finally:
        app.dependency_overrides.clear()


def test_provider_failure_is_persisted_as_failed_not_empty_result(document_users) -> None:
    class FakeOCR:
        name = "fake-ocr"

        def extract(self, content: bytes, content_type: str):
            return [OCRPage(page=1, text="readable synthetic text", readable=True, source="embedded_text")]

    class FailingAI:
        name = "failing-ai"

        def extract(self, pages, document_type):
            raise AIProviderError("synthetic provider outage")

    class SuccessfulAI:
        name = "successful-ai"

        def extract(self, pages, document_type):
            return ExtractionResult(document_type=document_type, pages=pages)

    app.dependency_overrides[get_ocr_provider] = lambda: FakeOCR()
    app.dependency_overrides[get_ai_provider] = lambda: SuccessfulAI()
    try:
        client = TestClient(app)
        assert login(client, document_users["executive_email"], EXECUTIVE_PASSWORD).status_code == 200
        shipment_id = create_shipment(client)
        upload = client.post(
            f"/api/v1/shipments/{shipment_id}/documents",
            data={"document_type": "INVOICE"},
            files={"file": ("invoice.pdf", PDF, "application/pdf")},
            headers=protected_write_headers(client),
        )
        assert upload.status_code == 201
        document_id = upload.json()["id"]

        first_attempt = client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{document_id}/extract",
            headers=protected_write_headers(client),
        )

        assert first_attempt.status_code == 200
        assert first_attempt.json()["result"] is not None

        app.dependency_overrides[get_ai_provider] = lambda: FailingAI()
        extracted = client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{document_id}/extract",
            headers=protected_write_headers(client),
        )

        assert extracted.status_code == 200
        assert extracted.json()["status"] == "FAILED"
        assert extracted.json()["error_code"] == "AI_PROVIDER_FAILED"
        assert extracted.json()["result"] is None
        assert extracted.json()["error_message"] == "Configured extraction provider failed"
    finally:
        app.dependency_overrides.clear()


def test_review_corrections_revisions_and_validation_staleness(document_users) -> None:
    class FakeOCR:
        name = "fake-ocr"

        def extract(self, content: bytes, content_type: str):
            return [OCRPage(page=1, text="synthetic", readable=True, source="embedded_text")]

    def extracted(value, confidence=0.95):
        return {"value": value, "confidence": confidence, "sources": [{"page": 1, "locator": "synthetic"}]}

    class FakeAI:
        name = "fake-ai"

        def extract(self, pages, document_type):
            return ExtractionResult(
                document_type=document_type,
                pages=pages,
                parties=PartyFields(
                    importer=ExtractedString(**extracted("Synthetic Importer")),
                    supplier=ExtractedString(**extracted("Synthetic Supplier", confidence=0.2)),
                ),
                invoice=InvoiceFields(
                    number=ExtractedString(**extracted("INV-EXPORT-1")),
                    date=ExtractedDate(**extracted(date(2026, 11, 5))),
                    currency=ExtractedString(),
                    incoterm=ExtractedString(**extracted("FOB")),
                    total=ExtractedDecimal(**extracted("16.32")),
                ),
                line_items=[
                    LineItem(
                        description=ExtractedString(**extracted("Synthetic item")),
                        quantity=ExtractedDecimal(**extracted("2")),
                        unit_price=ExtractedDecimal(**extracted("8.16")),
                    )
                ],
                shipment=ShipmentFields(
                    packages=ExtractedInteger(**extracted(10)),
                    gross_weight_kg=ExtractedDecimal(**extracted("100")),
                    net_weight_kg=ExtractedDecimal(**extracted("90")),
                ),
            )

    app.dependency_overrides[get_ocr_provider] = lambda: FakeOCR()
    app.dependency_overrides[get_ai_provider] = lambda: FakeAI()
    try:
        client = TestClient(app)
        manager = TestClient(app)
        assert login(client, document_users["executive_email"], EXECUTIVE_PASSWORD).status_code == 200
        assert login(manager, document_users["manager_email"], MANAGER_PASSWORD).status_code == 200
        shipment_id = create_shipment(client)
        document_ids = {}
        for document_type, filename in (("INVOICE", "invoice.pdf"), ("PACKING_LIST", "packing.pdf"), ("BILL_OF_LADING", "bol.pdf")):
            uploaded = client.post(
                f"/api/v1/shipments/{shipment_id}/documents",
                data={"document_type": document_type},
                files={"file": (filename, PDF, "application/pdf")},
                headers=protected_write_headers(client),
            )
            assert uploaded.status_code == 201
            document_id = uploaded.json()["id"]
            document_ids[document_type] = document_id
            extracted_response = client.post(
                f"/api/v1/shipments/{shipment_id}/documents/{document_id}/extract",
                headers=protected_write_headers(client),
            )
            assert extracted_response.status_code == 200

        review = client.get(f"/api/v1/shipments/{shipment_id}/review")
        assert review.status_code == 200
        packing = next(item for item in review.json()["documents"] if item["document_type"] == "PACKING_LIST")
        bill_of_lading = next(item for item in review.json()["documents"] if item["document_type"] == "BILL_OF_LADING")
        assert not any(field["field_path"].startswith("invoice.") for field in packing["fields"])
        assert not any(field["field_path"].startswith("invoice.") for field in bill_of_lading["fields"])
        gross_field = next(item for item in packing["fields"] if item["field_path"] == "shipment.gross_weight_kg")
        invoice = next(item for item in review.json()["documents"] if item["document_type"] == "INVOICE")
        invoice_number = next(item for item in invoice["fields"] if item["field_path"] == "invoice.number")
        invoice_currency = next(item for item in invoice["fields"] if item["field_path"] == "invoice.currency")

        before_review = client.get(f"/api/v1/shipments/{shipment_id}/export-eligibility")
        assert before_review.status_code == 200
        assert any(
            item["code"] == "LOW_CONFIDENCE_FIELD"
            and item["field_path"] == "parties.supplier"
            for item in before_review.json()["blockers"]
        )

        corrected_currency = client.patch(
            f"/api/v1/fields/{invoice_currency['id']}",
            json={"value": "USD", "expected_version": invoice_currency["version"]},
            headers=protected_write_headers(client),
        )
        assert corrected_currency.status_code == 200
        assert corrected_currency.json()["status"] == "CORRECTED"
        assert corrected_currency.json()["confidence"] is None
        assert corrected_currency.json()["source_references"] == []

        confirmed_currency = client.post(
            f"/api/v1/fields/{invoice_currency['id']}/confirm",
            json={"expected_version": corrected_currency.json()["version"]},
            headers=protected_write_headers(client),
        )
        assert confirmed_currency.status_code == 200
        assert confirmed_currency.json()["status"] == "CONFIRMED"
        assert confirmed_currency.json()["confidence"] is None
        assert confirmed_currency.json()["source_references"] == []

        csrfless_confirm = client.post(
            f"/api/v1/fields/{gross_field['id']}/confirm",
            json={"expected_version": gross_field["version"]},
            headers={"Origin": ORIGIN},
        )
        csrfless_correction = client.patch(
            f"/api/v1/fields/{gross_field['id']}",
            json={"value": "101", "expected_version": gross_field["version"]},
            headers={"Origin": ORIGIN},
        )
        csrfless_rejection = client.post(
            f"/api/v1/fields/{invoice_number['id']}/reject",
            json={"expected_version": invoice_number["version"]},
            headers={"Origin": ORIGIN},
        )
        assert all(
            response.status_code == 403
            and response.json()["error"]["code"] == "CSRF_FAILED"
            for response in (csrfless_confirm, csrfless_correction, csrfless_rejection)
        )

        checks = client.post(
            f"/api/v1/shipments/{shipment_id}/validations/run",
            headers=protected_write_headers(client),
        )
        assert checks.status_code == 200
        assert all(item["status"] == "PASSED" for item in checks.json()["validations"])

        concurrent_clients = [TestClient(app), TestClient(app)]
        for concurrent_client in concurrent_clients:
            assert login(
                concurrent_client,
                document_users["executive_email"],
                EXECUTIVE_PASSWORD,
            ).status_code == 200

        first_confirm = concurrent_clients[0].post(
            f"/api/v1/fields/{gross_field['id']}/confirm",
            json={"expected_version": gross_field["version"]},
            headers=protected_write_headers(concurrent_clients[0]),
        )
        stale_confirm = concurrent_clients[1].post(
            f"/api/v1/fields/{gross_field['id']}/confirm",
            json={"expected_version": gross_field["version"]},
            headers=protected_write_headers(concurrent_clients[1]),
        )
        assert first_confirm.status_code == 200
        assert stale_confirm.status_code == 409

        for document in review.json()["documents"]:
            for field in document["fields"]:
                if field["value"] is not None and field["id"] != gross_field["id"]:
                    confirmed_field = client.post(
                        f"/api/v1/fields/{field['id']}/confirm",
                        json={"expected_version": field["version"]},
                        headers=protected_write_headers(client),
                    )
                    assert confirmed_field.status_code == 200
        eligible = client.get(f"/api/v1/shipments/{shipment_id}/export-eligibility")
        assert eligible.status_code == 200
        assert eligible.json()["eligible"] is True
        assert not any(
            item["code"] == "LOW_CONFIDENCE_FIELD"
            and item["field_path"] == "invoice.currency"
            for item in eligible.json()["blockers"]
        )
        exported = client.post(
            f"/api/v1/shipments/{shipment_id}/exports",
            headers=protected_write_headers(client),
        )
        assert exported.status_code == 200
        assert "shipment_reference" in exported.text
        assert "Synthetic item" in exported.text

        corrected = client.patch(
            f"/api/v1/fields/{gross_field['id']}",
            json={"value": "101", "note": "Synthetic correction", "expected_version": 2},
            headers=protected_write_headers(client),
        )
        assert corrected.status_code == 200
        assert corrected.json()["status"] == "CORRECTED"
        assert corrected.json()["version"] == 3
        stale = client.get(f"/api/v1/shipments/{shipment_id}/validations")
        assert stale.status_code == 200
        assert all(item["status"] == "STALE" for item in stale.json())
        stale_eligibility = client.get(f"/api/v1/shipments/{shipment_id}/export-eligibility")
        assert stale_eligibility.status_code == 200
        assert stale_eligibility.json()["eligible"] is False
        assert any(
            item["code"] == "VALIDATION_NOT_PASSED"
            for item in stale_eligibility.json()["blockers"]
        )

        rerun = client.post(
            f"/api/v1/shipments/{shipment_id}/validations/run",
            headers=protected_write_headers(client),
        )
        assert rerun.status_code == 200
        gross_check = next(item for item in rerun.json()["validations"] if item["rule_key"] == "gross_weight_across_documents")
        assert gross_check["status"] == "FAILED"
        assert gross_check["details"]["comparison"] == "different"

        confirmed = client.post(
            f"/api/v1/fields/{gross_field['id']}/confirm",
            json={"expected_version": 3},
            headers=protected_write_headers(client),
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "CONFIRMED"

        rejected = client.post(
            f"/api/v1/fields/{invoice_number['id']}/reject",
            json={"note": "Not present in synthetic source", "expected_version": 2},
            headers=protected_write_headers(client),
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "REJECTED"
        blocked = client.get(f"/api/v1/shipments/{shipment_id}/export-eligibility")
        assert blocked.status_code == 200
        assert blocked.json()["eligible"] is False
        assert any(item["code"] == "REJECTED_FIELD" for item in blocked.json()["blockers"])
        blocked_export = client.post(
            f"/api/v1/shipments/{shipment_id}/exports",
            headers=protected_write_headers(client),
        )
        assert blocked_export.status_code == 409
        assert blocked_export.json()["error"]["code"] == "EXPORT_BLOCKED"

        revisions = client.get(f"/api/v1/fields/{gross_field['id']}/revisions")
        assert revisions.status_code == 200
        assert [item["action"] for item in revisions.json()] == ["EXTRACTED", "CONFIRMED", "CORRECTED", "CONFIRMED"]

        report = manager.get("/api/v1/reports/accuracy")
        assert report.status_code == 200
        supplier = next(item for item in report.json()["supplier_metrics"] if item["key"] == "Synthetic Supplier GmbH")
        assert supplier["corrected_count"] >= 1
        assert supplier["rejected_count"] >= 1
    finally:
        app.dependency_overrides.clear()


def test_extraction_rerun_reconciles_removed_line_items_and_containers(document_users) -> None:
    class FakeOCR:
        name = "fake-ocr"

        def extract(self, content: bytes, content_type: str):
            return [OCRPage(page=1, text="synthetic", readable=True, source="embedded_text")]

    def extracted(value):
        return {"value": value, "confidence": 0.95, "sources": [{"page": 1, "locator": "synthetic"}]}

    class MutableAI:
        name = "mutable-ai"

        def __init__(self):
            self.calls = 0

        def extract(self, pages, document_type):
            item_count = 2 if self.calls == 0 else 1
            self.calls += 1
            return ExtractionResult(
                document_type=document_type,
                pages=pages,
                line_items=[
                    LineItem(
                        description=ExtractedString(**extracted(f"Synthetic item {index}")),
                        quantity=ExtractedDecimal(**extracted(str(index))),
                        unit_price=ExtractedDecimal(**extracted("10.00")),
                    )
                    for index in range(1, item_count + 1)
                ],
                shipment=ShipmentFields(
                    containers=[
                        ExtractedString(**extracted(f"CONT000000{index}"))
                        for index in range(1, item_count + 1)
                    ]
                ),
            )

    ai = MutableAI()
    app.dependency_overrides[get_ocr_provider] = lambda: FakeOCR()
    app.dependency_overrides[get_ai_provider] = lambda: ai
    try:
        client = TestClient(app)
        assert login(client, document_users["executive_email"], EXECUTIVE_PASSWORD).status_code == 200
        shipment_id = create_shipment(client)
        uploaded = client.post(
            f"/api/v1/shipments/{shipment_id}/documents",
            data={"document_type": "INVOICE"},
            files={"file": ("invoice.pdf", PDF, "application/pdf")},
            headers=protected_write_headers(client),
        )
        assert uploaded.status_code == 201
        document_id = uploaded.json()["id"]

        first = client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{document_id}/extract",
            headers=protected_write_headers(client),
        )
        assert first.status_code == 200
        second = client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{document_id}/extract",
            headers=protected_write_headers(client),
        )
        assert second.status_code == 200

        review = client.get(f"/api/v1/shipments/{shipment_id}/review")
        assert review.status_code == 200
        fields = {field["field_path"]: field for field in review.json()["documents"][0]["fields"]}
        assert fields["line_items[0].description"]["value"] == "Synthetic item 1"
        assert fields["shipment.containers[0]"]["value"] == "CONT0000001"
        session = get_session_factory()()
        try:
            persisted = {
                field.field_path: field
                for field in session.scalars(
                    select(ReviewField).where(ReviewField.document_id == document_id)
                )
            }
            assert persisted["line_items[1].description"].current_value is None
            assert persisted["line_items[1].description"].status == "NEEDS_REVIEW"
            assert persisted["shipment.containers[1]"].current_value is None
            assert persisted["shipment.containers[1]"].status == "NEEDS_REVIEW"
        finally:
            session.close()
    finally:
        app.dependency_overrides.clear()


def test_real_sample_documents_complete_workflow(document_users) -> None:
    """Exercise the production local OCR and labelled-text providers end to end."""

    sample_dir = Path(__file__).parents[3] / "output" / "demo-documents"
    sample_documents = (
        ("INVOICE", "01_Commercial_Invoice.pdf"),
        ("PACKING_LIST", "02_Packing_List.pdf"),
        ("BILL_OF_LADING", "03_Bill_of_Lading.pdf"),
    )
    for _document_type, filename in sample_documents:
        assert (sample_dir / filename).is_file(), f"missing real sample PDF: {filename}"

    expected = {
        "INVOICE": {
            "parties": {
                "importer": "Northstar Automation GmbH",
                "supplier": "Apex Motion Systems Pvt. Ltd.",
            },
            "invoice": {
                "number": "INV-2026-1105-073",
                "date": "2026-11-05",
                "currency": "USD",
                "incoterm": "FOB",
                "total": "22000.00",
            },
            "line_items": [
                ("Industrial servo drive controller", "12", "1250.00", "85044090"),
                ("Motion control gateway", "8", "875.00", "85371099"),
            ],
        },
        "PACKING_LIST": {
            "parties": {
                "exporter": "Apex Motion Systems Pvt. Ltd.",
                "consignee": "Northstar Automation GmbH",
            },
            "invoice": {},
            "line_items": [],
        },
        "BILL_OF_LADING": {
            "parties": {
                "exporter": "Apex Motion Systems Pvt. Ltd.",
                "consignee": "Northstar Automation GmbH",
            },
            "invoice": {},
            "line_items": [],
        },
    }

    def assert_field_evidence(field: dict) -> None:
        if field["value"] is None:
            assert field["confidence"] is None
            assert field["sources"] == []
            return
        assert field["confidence"] is not None
        assert 0 <= field["confidence"] <= 1
        assert field["sources"]
        assert all(source["page"] == 1 and source["locator"] for source in field["sources"])

    client = TestClient(app)
    assert login(client, document_users["executive_email"], EXECUTIVE_PASSWORD).status_code == 200
    shipment_id = create_shipment(client)
    document_ids: dict[str, str] = {}

    for document_type, filename in sample_documents:
        uploaded = client.post(
            f"/api/v1/shipments/{shipment_id}/documents",
            data={"document_type": document_type},
            files={"file": (filename, (sample_dir / filename).read_bytes(), "application/pdf")},
            headers=protected_write_headers(client),
        )
        assert uploaded.status_code == 201
        document_id = uploaded.json()["id"]
        document_ids[document_type] = document_id

        extracted = client.post(
            f"/api/v1/shipments/{shipment_id}/documents/{document_id}/extract",
            headers=protected_write_headers(client),
        )
        assert extracted.status_code == 200
        payload = extracted.json()
        assert payload["status"] == "SUCCEEDED"
        assert payload["provider_name"] == "local-labelled-text"
        assert payload["ocr_provider_name"] == "local-pypdf-tesseract"
        assert payload["page_count"] == 1
        result = payload["result"]
        assert result["document_type"] == document_type
        assert result["pages"] == [
            {
                "page": 1,
                "text": result["pages"][0]["text"],
                "readable": True,
                "source": "embedded_text",
            }
        ]
        assert result["pages"][0]["text"]
        for group in (result["parties"], result["invoice"], result["shipment"]):
            for field in group.values():
                if isinstance(field, dict):
                    assert_field_evidence(field)
        for item in result["line_items"]:
            for field in item.values():
                assert_field_evidence(field)
        for container in result["shipment"]["containers"]:
            assert_field_evidence(container)

        for group_name, fields in expected[document_type].items():
            if group_name == "line_items":
                assert [
                    (
                        item["description"]["value"],
                        item["quantity"]["value"],
                        item["unit_price"]["value"],
                        item["hsn_code"]["value"],
                    )
                    for item in result["line_items"]
                ] == fields
            else:
                for field_name, value in fields.items():
                    assert result[group_name][field_name]["value"] == value
        assert result["shipment"]["packages"]["value"] == 4
        assert result["shipment"]["gross_weight_kg"]["value"] == "380"
        assert result["shipment"]["net_weight_kg"]["value"] == "320"
        assert [item["value"] for item in result["shipment"]["containers"]] == ["MSCU1234567"]

    review = client.get(f"/api/v1/shipments/{shipment_id}/review")
    assert review.status_code == 200
    review_documents = {item["document_type"]: item for item in review.json()["documents"]}
    assert set(review_documents) == {document_type for document_type, _ in sample_documents}
    initial_eligibility = client.get(f"/api/v1/shipments/{shipment_id}/export-eligibility")
    assert initial_eligibility.status_code == 200
    assert initial_eligibility.json()["eligible"] is False

    invoice_fields = {field["field_path"]: field for field in review_documents["INVOICE"]["fields"]}
    invoice_number = invoice_fields["invoice.number"]
    corrected = client.patch(
        f"/api/v1/fields/{invoice_number['id']}",
        json={
            "value": "INV-2026-1105-073-REV1",
            "note": "Verified against the original sample PDF",
            "expected_version": invoice_number["version"],
        },
        headers=protected_write_headers(client),
    )
    assert corrected.status_code == 200
    assert corrected.json()["status"] == "CORRECTED"
    confirmed = client.post(
        f"/api/v1/fields/{invoice_number['id']}/confirm",
        json={"expected_version": corrected.json()["version"]},
        headers=protected_write_headers(client),
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "CONFIRMED"

    reloaded = client.get(f"/api/v1/shipments/{shipment_id}/review")
    reloaded_invoice = next(
        item for item in reloaded.json()["documents"] if item["document_type"] == "INVOICE"
    )
    persisted_number = next(
        field for field in reloaded_invoice["fields"] if field["field_path"] == "invoice.number"
    )
    assert persisted_number["value"] == "INV-2026-1105-073-REV1"
    assert persisted_number["status"] == "CONFIRMED"

    for document in reloaded.json()["documents"]:
        for field in document["fields"]:
            if field["value"] is not None and field["status"] != "CONFIRMED":
                response = client.post(
                    f"/api/v1/fields/{field['id']}/confirm",
                    json={"expected_version": field["version"]},
                    headers=protected_write_headers(client),
                )
                assert response.status_code == 200
                assert response.json()["status"] == "CONFIRMED"

    validations = client.post(
        f"/api/v1/shipments/{shipment_id}/validations/run",
        headers=protected_write_headers(client),
    )
    assert validations.status_code == 200
    assert {item["status"] for item in validations.json()["validations"]} == {"PASSED"}

    eligible = client.get(f"/api/v1/shipments/{shipment_id}/export-eligibility")
    assert eligible.status_code == 200
    assert eligible.json() == {"eligible": True, "blockers": []}
    exported = client.post(
        f"/api/v1/shipments/{shipment_id}/exports",
        headers=protected_write_headers(client),
    )
    assert exported.status_code == 200
    rows = list(csv.DictReader(StringIO(exported.text)))
    assert len(rows) == 2
    assert rows[0]["invoice_number"] == "INV-2026-1105-073-REV1"
    assert [row["item_description"] for row in rows] == [
        "Industrial servo drive controller",
        "Motion control gateway",
    ]
    assert all(row["shipment_reference"] == rows[0]["shipment_reference"] for row in rows)
    assert all(row["packages"] == "4" and row["gross_weight_kg"] == "380" for row in rows)
    assert all(row["net_weight_kg"] == "320" and row["containers"] == "MSCU1234567" for row in rows)
