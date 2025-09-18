"""Document ingestion and storage helpers.

This module owns the logic that writes uploaded files into the document
storage directory under ``var/documents/`` and exposes metadata lookup
utilities for API routes and background jobs. The implementation favours a
straightforward "always store a new file" approach: every upload is written
under a randomly generated path, and metadata is persisted alongside the
stored bytes. This keeps the service easy to reason about without the
complexity of deduplication or restoration logic.
"""

from __future__ import annotations

import io
import secrets
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import Document

_HASH_PREFIX = "sha256:"
_CHUNK_SIZE = 1024 * 1024
_MAX_STORAGE_KEY_ATTEMPTS = 10


class DocumentNotFoundError(Exception):
    """Raised when a document identifier cannot be located."""

    def __init__(self, document_id: str) -> None:
        message = f"Document '{document_id}' was not found"
        super().__init__(message)
        self.document_id = document_id


class DocumentTooLargeError(Exception):
    """Raised when an uploaded payload exceeds the configured limit."""

    def __init__(self, *, limit: int, received: int) -> None:
        self.limit = limit
        self.received = received
        message = (
            f"Uploaded file is {_format_size(received)} ({received:,} bytes), "
            f"exceeding the configured limit of {_format_size(limit)} ({limit:,} bytes)."
        )
        super().__init__(message)


class InvalidDocumentExpirationError(Exception):
    """Raised when an ``expires_at`` override cannot be processed."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


def _format_size(value: int) -> str:
    units = ("bytes", "KiB", "MiB", "GiB", "TiB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "bytes":
                return f"{int(size):,} {unit}"
            return f"{size:.2f} {unit}"
        size /= 1024


def _normalise_filename(name: str | None) -> str:
    if name is None:
        return "upload"
    stripped = name.strip()
    return stripped or "upload"


def _normalise_content_type(content_type: str | None) -> str | None:
    if content_type is None:
        return None
    stripped = content_type.strip()
    return stripped or None


def _as_stream(data: bytes | BinaryIO) -> BinaryIO:
    if isinstance(data, (bytes, bytearray)):
        return io.BytesIO(data)
    return data


def _rewind(stream: BinaryIO) -> None:
    try:
        if hasattr(stream, "seek") and stream.seekable():
            stream.seek(0)
    except Exception:  # pragma: no cover - defensive fallback
        pass


def _generate_storage_token() -> str:
    return secrets.token_hex(32)


def _relative_storage_path(token: str) -> Path:
    return Path(token[:2]) / token[2:4] / token


def _reserve_storage_path(documents_dir: Path) -> tuple[Path, Path]:
    for _ in range(_MAX_STORAGE_KEY_ATTEMPTS):
        token = _generate_storage_token()
        relative = _relative_storage_path(token)
        candidate = documents_dir / relative
        if not candidate.exists():
            return relative, candidate
    raise RuntimeError("Unable to allocate unique storage path")


def _write_stream_to_path(
    stream: BinaryIO,
    destination: Path,
    *,
    max_bytes: int | None = None,
) -> tuple[str, int]:
    size = 0
    hasher = sha256()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("wb") as target:
            while True:
                chunk = stream.read(_CHUNK_SIZE)
                if not chunk:
                    break
                prospective_size = size + len(chunk)
                if max_bytes is not None and prospective_size > max_bytes:
                    raise DocumentTooLargeError(
                        limit=max_bytes, received=prospective_size
                    )
                target.write(chunk)
                hasher.update(chunk)
                size = prospective_size
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    digest = hasher.hexdigest()
    return digest, size


def _resolve_expiration(
    *, override: str | None, now: datetime, retention_days: int
) -> datetime:
    if override is None:
        return now + timedelta(days=retention_days)

    candidate = override.strip()
    if candidate.endswith(("Z", "z")):
        candidate = f"{candidate[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        message = "expires_at must be a valid ISO 8601 timestamp"
        raise InvalidDocumentExpirationError(message) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)

    if parsed <= now:
        message = "expires_at must be in the future"
        raise InvalidDocumentExpirationError(message)

    return parsed
    


def store_document(
    db: Session,
    *,
    original_filename: str | None,
    content_type: str | None,
    data: bytes | BinaryIO,
    expires_at: str | None = None,
) -> Document:
    """Persist a document to disk and return the metadata record.

    Every upload is assigned a unique on-disk location under the configured
    documents directory. The stored file path is randomised so callers do not
    need to coordinate file names ahead of time.
    """

    settings = config.get_settings()
    stream = _as_stream(data)
    _rewind(stream)

    relative_path, stored_path = _reserve_storage_path(settings.documents_dir)
    digest, size = _write_stream_to_path(
        stream, stored_path, max_bytes=settings.max_upload_bytes
    )
    sha_value = f"{_HASH_PREFIX}{digest}"
    stored_uri = relative_path.as_posix()

    now = datetime.now(timezone.utc)
    expiration = _resolve_expiration(
        override=expires_at,
        now=now,
        retention_days=settings.default_document_retention_days,
    ).isoformat()
    now_iso = now.isoformat()

    document = Document(
        original_filename=_normalise_filename(original_filename),
        content_type=_normalise_content_type(content_type),
        byte_size=size,
        sha256=sha_value,
        stored_uri=stored_uri,
        metadata_={},
        expires_at=expiration,
        created_at=now_iso,
        updated_at=now_iso,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def list_documents(db: Session, *, include_deleted: bool = False) -> list[Document]:
    """Return documents ordered by creation time (newest first)."""

    statement = select(Document).order_by(Document.created_at.desc())
    if not include_deleted:
        statement = statement.where(Document.deleted_at.is_(None))
    return list(db.scalars(statement))


def get_document(db: Session, document_id: str) -> Document:
    """Fetch a document by identifier."""

    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(document_id)
    return document


def resolve_document_path(
    document: Document, *, settings: config.Settings | None = None
) -> Path:
    """Return the on-disk path for the stored document."""

    settings = settings or config.get_settings()
    stored_path = Path(document.stored_uri)
    if stored_path.is_absolute():
        return stored_path
    return settings.documents_dir / stored_path


def delete_document(
    db: Session,
    document_id: str,
    *,
    deleted_by: str,
    delete_reason: str | None = None,
) -> Document:
    """Soft delete a document and remove the stored file when present."""

    document = get_document(db, document_id)
    now = datetime.now(timezone.utc)
    settings = config.get_settings()
    path = resolve_document_path(document, settings=settings)
    path.unlink(missing_ok=True)

    if document.deleted_at is None:
        now_iso = now.isoformat()
        document.deleted_at = now_iso
        document.deleted_by = deleted_by
        document.delete_reason = delete_reason
        document.updated_at = now_iso
        db.add(document)
        db.commit()
        db.refresh(document)
    else:
        db.commit()

    return document


def iter_document_file(
    document: Document,
    *,
    settings: config.Settings | None = None,
    chunk_size: int = _CHUNK_SIZE,
) -> Iterator[bytes]:
    """Yield document bytes in chunks suitable for streaming responses."""

    path = resolve_document_path(document, settings=settings)
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            yield chunk


__all__ = [
    "DocumentNotFoundError",
    "DocumentTooLargeError",
    "InvalidDocumentExpirationError",
    "store_document",
    "list_documents",
    "get_document",
    "resolve_document_path",
    "delete_document",
    "iter_document_file",
]
