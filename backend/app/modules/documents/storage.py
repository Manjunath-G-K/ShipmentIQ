"""Provider-neutral private document storage with content validation."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4


CHUNK_SIZE = 1024 * 1024
_STORAGE_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}\.(pdf|jpg|png)$")
_ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}
_GENERIC_CONTENT_TYPES = {"", "application/octet-stream", "binary/octet-stream"}


class InvalidStoredDocumentError(ValueError):
    """The upload does not match the allowed file types or configured limits."""


class DocumentStorageError(OSError):
    """The private storage provider could not read or write a document."""


@dataclass(frozen=True)
class StoredFile:
    original_filename: str
    storage_key: str
    content_type: str
    size_bytes: int
    sha256: str


class DocumentStorage(Protocol):
    """Storage contract allowing a future India-hosted provider to be injected."""

    def save(
        self,
        source: BinaryIO,
        *,
        filename: str | None,
        declared_content_type: str | None,
    ) -> StoredFile: ...

    def open(self, storage_key: str) -> BinaryIO: ...

    def delete(self, storage_key: str) -> None: ...


def _safe_original_filename(filename: str | None) -> str:
    if not filename:
        raise InvalidStoredDocumentError("A filename is required")
    if any(ord(character) < 32 or ord(character) == 127 for character in filename):
        raise InvalidStoredDocumentError("Filename contains invalid control characters")
    basename = Path(filename).name.strip()
    if not basename or len(basename) > 255:
        raise InvalidStoredDocumentError("Filename must be between 1 and 255 characters")
    return basename


def _validate_content(prefix: bytes, suffix: bytes, size_bytes: int) -> tuple[str, str]:
    if (
        prefix.startswith(b"%PDF-1.")
        and size_bytes >= 8
        and b"%%EOF" in suffix
    ):
        return ".pdf", "application/pdf"

    if prefix.startswith(b"\x89PNG\r\n\x1a\n") and size_bytes >= 33:
        # Validate the required IHDR chunk, dimensions, and CRC rather than only the signature.
        ihdr_length = int.from_bytes(prefix[8:12], "big")
        width = int.from_bytes(prefix[16:20], "big")
        height = int.from_bytes(prefix[20:24], "big")
        expected_crc = int.from_bytes(prefix[29:33], "big")
        actual_crc = zlib.crc32(prefix[12:29]) & 0xFFFFFFFF
        if (
            prefix[12:16] == b"IHDR"
            and ihdr_length == 13
            and width > 0
            and height > 0
            and actual_crc == expected_crc
        ):
            return ".png", "image/png"

    if prefix.startswith(b"\xff\xd8\xff") and b"\xff\xd9" in suffix:
        return ".jpg", "image/jpeg"

    raise InvalidStoredDocumentError("File content is not a supported PDF, JPG, or PNG")


class PrivateFileStorage:
    """Local private storage implementation behind a replaceable provider boundary."""

    def __init__(self, base_path: Path, max_size_bytes: int) -> None:
        self.base_path = base_path.expanduser()
        self.max_size_bytes = max_size_bytes

    def _ensure_base_path(self) -> None:
        try:
            self.base_path.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not self.base_path.is_dir():
                raise DocumentStorageError("Document storage path is not a directory")
            os.chmod(self.base_path, 0o700)
        except OSError as exc:
            raise DocumentStorageError("Document storage path is unavailable") from exc

    def _path_for_key(self, storage_key: str) -> Path:
        if not _STORAGE_KEY_PATTERN.fullmatch(storage_key):
            raise DocumentStorageError("Invalid private storage key")
        candidate = self.base_path / storage_key
        try:
            base_path = self.base_path.resolve(strict=False)
            resolved_candidate = candidate.resolve(strict=False)
            if not resolved_candidate.is_relative_to(base_path):
                raise DocumentStorageError("Invalid private storage key")
            if candidate.is_symlink():
                raise DocumentStorageError("Invalid private storage key")
        except OSError as exc:
            raise DocumentStorageError("Private storage path is unavailable") from exc
        return candidate

    def save(
        self,
        source: BinaryIO,
        *,
        filename: str | None,
        declared_content_type: str | None,
    ) -> StoredFile:
        original_filename = _safe_original_filename(filename)
        suffix = Path(original_filename).suffix.casefold()
        if suffix not in _ALLOWED_SUFFIXES:
            raise InvalidStoredDocumentError("File extension must be .pdf, .jpg, .jpeg, or .png")

        self._ensure_base_path()
        temporary_path: Path | None = None
        destination_path: Path | None = None
        destination_created = False
        size_bytes = 0
        digest = hashlib.sha256()
        prefix = b""
        suffix_bytes = b""
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".upload-", suffix=".tmp", dir=self.base_path
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as destination:
                while True:
                    chunk = source.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    if not isinstance(chunk, bytes):
                        raise InvalidStoredDocumentError("Uploaded file is not binary data")
                    size_bytes += len(chunk)
                    if size_bytes > self.max_size_bytes:
                        raise InvalidStoredDocumentError("File exceeds the configured size limit")
                    digest.update(chunk)
                    if len(prefix) < 64:
                        prefix += chunk[: 64 - len(prefix)]
                    suffix_bytes = (suffix_bytes + chunk)[-1024:]
                    destination.write(chunk)

            detected_suffix, content_type = _validate_content(
                prefix, suffix_bytes, size_bytes
            )
            normalized_declared_type = (declared_content_type or "").casefold()
            if normalized_declared_type not in _GENERIC_CONTENT_TYPES:
                accepted_types = {
                    "image/jpeg": {"image/jpeg", "image/jpg"},
                    "image/png": {"image/png"},
                    "application/pdf": {"application/pdf"},
                }[content_type]
                if normalized_declared_type not in accepted_types:
                    raise InvalidStoredDocumentError("Declared content type does not match file content")
            if suffix == ".jpeg":
                suffix = ".jpg"
            if suffix != detected_suffix:
                raise InvalidStoredDocumentError("Filename extension does not match file content")

            storage_key = f"{uuid4().hex}{detected_suffix}"
            destination_path = self.base_path / storage_key
            try:
                destination_descriptor = os.open(
                    destination_path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
            except FileExistsError as exc:
                raise DocumentStorageError("Generated storage filename collision") from exc
            destination_created = True
            with os.fdopen(destination_descriptor, "wb") as destination:
                with temporary_path.open("rb") as source:
                    shutil.copyfileobj(source, destination, CHUNK_SIZE)
            temporary_path.unlink()
            temporary_path = None
            destination_created = False
            return StoredFile(
                original_filename=original_filename,
                storage_key=storage_key,
                content_type=content_type,
                size_bytes=size_bytes,
                sha256=digest.hexdigest(),
            )
        except (InvalidStoredDocumentError, DocumentStorageError):
            raise
        except OSError as exc:
            raise DocumentStorageError("Document storage write failed") from exc
        finally:
            if destination_created and destination_path is not None:
                try:
                    destination_path.unlink(missing_ok=True)
                except OSError:
                    pass
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def open(self, storage_key: str) -> BinaryIO:
        safe_path = self._path_for_key(storage_key)
        try:
            return safe_path.open("rb")
        except FileNotFoundError as exc:
            raise FileNotFoundError from exc
        except OSError as exc:
            raise DocumentStorageError("Document storage read failed") from exc

    def delete(self, storage_key: str) -> None:
        safe_path = self._path_for_key(storage_key)
        try:
            safe_path.unlink(missing_ok=True)
        except OSError as exc:
            raise DocumentStorageError("Document storage cleanup failed") from exc
