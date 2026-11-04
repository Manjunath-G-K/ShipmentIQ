"""Unit tests for the provider-neutral private document storage adapter."""

from io import BytesIO
import struct
from uuid import UUID
import zlib

import pytest

from app.modules.documents.storage import (
    DocumentStorageError,
    InvalidStoredDocumentError,
    PrivateFileStorage,
)


PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
_PNG_IHDR = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
PNG = (
    b"\x89PNG\r\n\x1a\n"
    + len(_PNG_IHDR).to_bytes(4, "big")
    + b"IHDR"
    + _PNG_IHDR
    + zlib.crc32(b"IHDR" + _PNG_IHDR).to_bytes(4, "big")
    + b"\x00\x00\x00\x00IEND\xaeB`\x82"
)
JPEG = b"\xff\xd8\xff\xe0synthetic-jpeg\xff\xd9"


def test_save_generates_private_safe_key_and_round_trips(tmp_path) -> None:
    storage = PrivateFileStorage(tmp_path / "private", max_size_bytes=1024)

    stored = storage.save(
        BytesIO(PDF),
        filename="../../invoice.pdf",
        declared_content_type="application/pdf",
    )

    assert stored.storage_key != "invoice.pdf"
    assert stored.storage_key.endswith(".pdf")
    assert (tmp_path / "private" / stored.storage_key).read_bytes() == PDF
    with storage.open(stored.storage_key) as document:
        assert document.read() == PDF


@pytest.mark.parametrize(
    ("filename", "content", "content_type"),
    [
        ("packing.png", PNG, "image/png"),
        ("bill.jpg", JPEG, "image/jpeg"),
    ],
)
def test_supported_image_types_are_content_validated(
    tmp_path, filename: str, content: bytes, content_type: str
) -> None:
    storage = PrivateFileStorage(tmp_path, max_size_bytes=1024)

    stored = storage.save(
        BytesIO(content), filename=filename, declared_content_type=content_type
    )

    assert stored.content_type == content_type


def test_invalid_content_extension_and_size_are_rejected(tmp_path) -> None:
    storage = PrivateFileStorage(tmp_path, max_size_bytes=len(PDF) - 1)

    with pytest.raises(InvalidStoredDocumentError, match="size limit"):
        storage.save(BytesIO(PDF), filename="invoice.pdf", declared_content_type="application/pdf")

    storage = PrivateFileStorage(tmp_path, max_size_bytes=1024)
    with pytest.raises(InvalidStoredDocumentError, match="supported"):
        storage.save(BytesIO(b"not a document"), filename="invoice.pdf", declared_content_type="application/pdf")
    with pytest.raises(InvalidStoredDocumentError, match="extension"):
        storage.save(BytesIO(PDF), filename="invoice.png", declared_content_type="application/pdf")


def test_storage_failures_are_explicit(tmp_path) -> None:
    storage_path = tmp_path / "not-a-directory"
    storage_path.write_bytes(b"occupied")
    storage = PrivateFileStorage(storage_path, max_size_bytes=1024)

    with pytest.raises(DocumentStorageError):
        storage.save(BytesIO(PDF), filename="invoice.pdf", declared_content_type="application/pdf")


def test_missing_private_file_is_not_silently_replaced(tmp_path) -> None:
    storage = PrivateFileStorage(tmp_path, max_size_bytes=1024)

    with pytest.raises(FileNotFoundError):
        storage.open("0" * 32 + ".pdf")


def test_storage_key_traversal_and_collisions_are_rejected(tmp_path, monkeypatch) -> None:
    storage = PrivateFileStorage(tmp_path, max_size_bytes=1024)

    with pytest.raises(DocumentStorageError):
        storage.open("../outside.pdf")

    fixed_uuid = UUID("12345678-1234-5678-1234-567812345678")
    monkeypatch.setattr("app.modules.documents.storage.uuid4", lambda: fixed_uuid)
    first = storage.save(
        BytesIO(PDF), filename="first.pdf", declared_content_type="application/pdf"
    )
    with pytest.raises(DocumentStorageError, match="collision"):
        storage.save(
            BytesIO(PDF), filename="second.pdf", declared_content_type="application/pdf"
        )
    assert (tmp_path / first.storage_key).read_bytes() == PDF
