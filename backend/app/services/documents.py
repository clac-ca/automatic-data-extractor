"""Document ingestion and storage helpers.

This module owns the logic that writes uploaded files into the document
storage directory under ``var/documents/`` and exposes metadata lookup
utilities for API routes and background jobs. The implementation favours a
straightforward "always store a new file" approach: every upload is written
under a ULID-named path, and metadata is persisted alongside the stored
bytes. This keeps the service easy to reason about without the complexity of
deduplication or restoration logic.
"""

from __future__ import annotations

import io
import logging
import ulid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import Document
from .events import EventRecord, record_event

_HASH_PREFIX = "sha256:"
_CHUNK_SIZE = 1024 * 1024
_UPLOAD_SUBDIR = "uploads"
_OUTPUT_SUBDIR = "output"
_ALLOWED_STORAGE_PREFIXES = {_UPLOAD_SUBDIR, _OUTPUT_SUBDIR}


logger = logging.getLogger(__name__)


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
            f"Uploaded file is {received:,} bytes, exceeding the configured "
            f"limit of {limit:,} bytes."
        )
        super().__init__(message)


class DocumentStoragePathError(RuntimeError):
    """Raised when a stored document URI resolves outside the documents directory."""

    def __init__(self, stored_uri: str) -> None:
        message = (
            "Document storage path is outside the configured documents directory "
            "and cannot be accessed safely"
        )
        super().__init__(message)
        self.stored_uri = stored_uri


class DocumentFileMissingError(Exception):
    """Raised when a document's stored bytes cannot be found."""

    def __init__(self, document_id: str) -> None:
        message = f"Stored file for document '{document_id}' is missing"
        super().__init__(message)
        self.document_id = document_id


class InvalidDocumentExpirationError(Exception):
    """Raised when an ``expires_at`` override cannot be processed."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
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


def _prepare_stream(data: bytes | BinaryIO) -> BinaryIO:
    """Return a binary stream positioned at the start of the payload."""

    if isinstance(data, (bytes, bytearray)):
        return io.BytesIO(data)

    stream = data
    try:
        stream.seek(0)
    except (AttributeError, OSError):  # pragma: no cover - optional reset best effort
        pass
    return stream


def _persist_stream(
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
    return hasher.hexdigest(), size


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

    Uploaded files are written to ``<documents_dir>/uploads/`` using the
    document identifier as the filename so paths remain predictable.
    """

    settings = config.get_settings()
    stream = _prepare_stream(data)

    document_id = str(ulid.new())
    stored_uri = f"{_UPLOAD_SUBDIR}/{document_id}"
    disk_path = settings.documents_dir / stored_uri

    digest, size = _persist_stream(
        stream, disk_path, max_bytes=settings.max_upload_bytes
    )
    sha_value = f"{_HASH_PREFIX}{digest}"

    now = datetime.now(timezone.utc)
    expiration = _resolve_expiration(
        override=expires_at,
        now=now,
        retention_days=settings.default_document_retention_days,
    ).isoformat()
    now_iso = now.isoformat()

    document = Document(
        document_id=document_id,
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
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to persist document metadata; removing stored bytes",
            extra={
                "stored_uri": stored_uri,
                "disk_path": str(disk_path),
            },
        )
        try:
            disk_path.unlink(missing_ok=True)
        except Exception:
            logger.exception(
                "Failed to remove stored file after database error",
                extra={
                    "stored_uri": stored_uri,
                    "disk_path": str(disk_path),
                },
            )
        raise

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


def update_document(
    db: Session,
    document_id: str,
    *,
    metadata: dict[str, Any] | None = None,
    event_type: str | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    actor_label: str | None = None,
    source: str | None = None,
    request_id: str | None = None,
    occurred_at: datetime | str | None = None,
    event_payload: dict[str, Any] | None = None,
) -> Document:
    """Apply metadata changes and optionally record a document event."""

    with db.begin():
        document = get_document(db, document_id)

        current_metadata = dict(document.metadata_ or {})
        changed_keys: set[str] = set()
        removed_keys: set[str] = set()
        metadata_updated = False

        if metadata is not None:
            for key, value in metadata.items():
                if value is None:
                    if key in current_metadata:
                        removed_keys.add(key)
                        metadata_updated = True
                        current_metadata.pop(key)
                else:
                    existing = current_metadata.get(key)
                    if existing != value:
                        current_metadata[key] = value
                        changed_keys.add(key)
                        metadata_updated = True

            if metadata_updated:
                document.metadata_ = current_metadata
                now_iso = datetime.now(timezone.utc).isoformat()
                document.updated_at = now_iso
            else:
                now_iso = None
        else:
            now_iso = None

        payload: dict[str, Any] = {}
        if metadata_updated:
            if changed_keys:
                payload["metadata"] = {
                    key: current_metadata[key] for key in sorted(changed_keys)
                }
            affected = changed_keys | removed_keys
            if affected:
                payload["changed_keys"] = sorted(affected)
            if removed_keys:
                payload["removed_keys"] = sorted(removed_keys)

        if event_payload:
            payload.update(event_payload)

        actor_label_value = actor_label or actor_id
        event_type_value = event_type or ("document.metadata.updated" if metadata_updated else None)
        occurred_at_value: datetime | str | None = occurred_at or now_iso

        if event_type_value is not None:
            if occurred_at_value is None:
                occurred_at_value = datetime.now(timezone.utc)

            event = EventRecord(
                event_type=event_type_value,
                entity_type="document",
                entity_id=document.document_id,
                actor_type=actor_type,
                actor_id=actor_id,
                actor_label=actor_label_value,
                source=source,
                request_id=request_id,
                occurred_at=occurred_at_value,
                payload=payload,
            )
            record_event(db, event, commit=False)

        db.add(document)

    db.refresh(document)
    return document


def resolve_document_path(
    document: Document, *, settings: config.Settings | None = None
) -> Path:
    """Return the on-disk path for the stored document."""

    settings = settings or config.get_settings()
    stored_uri = (document.stored_uri or "").strip()
    if not stored_uri:
        raise DocumentStoragePathError(document.stored_uri or "")

    base_dir = settings.documents_dir.resolve()
    relative_path = Path(stored_uri)

    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise DocumentStoragePathError(document.stored_uri)

    if not relative_path.parts or relative_path.parts[0] not in _ALLOWED_STORAGE_PREFIXES:
        raise DocumentStoragePathError(document.stored_uri)

    return (base_dir / relative_path).resolve()


def _ensure_document_file(
    document: Document, *, settings: config.Settings
) -> Path:
    """Return the path to the stored document, raising if the file is missing."""

    path = resolve_document_path(document, settings=settings)
    if not path.exists():
        raise DocumentFileMissingError(document.document_id)
    return path


def delete_document(
    db: Session,
    document_id: str,
    *,
    deleted_by: str,
    delete_reason: str | None = None,
    commit: bool = True,
    event_actor_type: str | None = None,
    event_actor_id: str | None = None,
    event_actor_label: str | None = None,
    event_source: str | None = None,
    event_request_id: str | None = None,
    event_payload: dict[str, Any] | None = None,
) -> Document:
    """Soft delete a document and remove the stored file.

    Raises:
        DocumentNotFoundError: If the document metadata cannot be located.
        DocumentStoragePathError: If the stored URI resolves outside the documents directory.
        DocumentFileMissingError: If the stored bytes are not present on disk.
    """

    document = get_document(db, document_id)
    settings = config.get_settings()

    path: Path | None = None
    mutated = document.deleted_at is None
    if mutated:
        path = _ensure_document_file(document, settings=settings)
        now_iso = datetime.now(timezone.utc).isoformat()
        document.deleted_at = now_iso
        document.deleted_by = deleted_by
        document.delete_reason = delete_reason
        document.updated_at = now_iso

    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        if mutated:
            db.refresh(document)
    elif mutated:
        db.flush()

    if path is not None:
        try:
            path.unlink()
        except FileNotFoundError as exc:
            raise DocumentFileMissingError(document.document_id) from exc
        except Exception:
            logger.exception(
                "Failed to remove stored bytes for document deletion",
                extra={
                    "document_id": document.document_id,
                    "stored_uri": document.stored_uri,
                },
            )
            raise

    if mutated:
        payload: dict[str, Any] = {
            "deleted_by": document.deleted_by,
            "delete_reason": document.delete_reason,
            "byte_size": document.byte_size,
            "stored_uri": document.stored_uri,
            "sha256": document.sha256,
            "expires_at": document.expires_at,
        }
        if event_payload:
            payload.update(event_payload)

        event = EventRecord(
            event_type="document.deleted",
            entity_type="document",
            entity_id=document.document_id,
            actor_type=event_actor_type,
            actor_id=event_actor_id,
            actor_label=event_actor_label or document.deleted_by,
            source=event_source,
            request_id=event_request_id,
            occurred_at=document.deleted_at,
            payload=payload,
        )

        try:
            record_event(db, event, commit=commit)
        except Exception:
            logger.exception(
                "Failed to record document deletion event",
                extra={
                    "document_id": document.document_id,
                    "event_type": "document.deleted",
                    "source": event_source,
                },
            )

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


@dataclass(slots=True)
class PurgedDocument:
    """Details about a document considered during a purge run."""

    document_id: str
    stored_uri: str
    expires_at: str
    byte_size: int


@dataclass(slots=True)
class ExpiredDocumentPurgeSummary:
    """Aggregated outcome of a purge run."""

    dry_run: bool
    processed_count: int = 0
    bytes_reclaimed: int = 0
    documents: list[PurgedDocument] = field(default_factory=list)

    def record(self, document: Document) -> None:
        self.processed_count += 1
        self.bytes_reclaimed += document.byte_size

        self.documents.append(
            PurgedDocument(
                document_id=document.document_id,
                stored_uri=document.stored_uri,
                expires_at=document.expires_at,
                byte_size=document.byte_size,
            )
        )


def iter_expired_documents(
    db: Session,
    *,
    batch_size: int = 100,
    limit: int | None = None,
) -> Iterator[list[Document]]:
    """Yield batches of expired, undeleted documents ordered by expiration."""

    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    now_iso = datetime.now(timezone.utc).isoformat()
    if limit is not None and limit <= 0:
        return

    statement = (
        select(Document)
        .where(Document.deleted_at.is_(None), Document.expires_at <= now_iso)
        .order_by(Document.expires_at.asc(), Document.document_id.asc())
    )

    if limit is not None:
        statement = statement.limit(limit)

    documents = list(db.scalars(statement))
    for start in range(0, len(documents), batch_size):
        yield documents[start : start + batch_size]


def purge_expired_documents(
    db: Session,
    *,
    limit: int | None = None,
    dry_run: bool = False,
    batch_size: int = 100,
    deleted_by: str = "maintenance:purge_expired_documents",
    delete_reason: str = "expired_document_purge",
    event_source: str = "scheduler",
    event_request_id: str | None = None,
) -> ExpiredDocumentPurgeSummary:
    """Remove expired documents and mark their metadata.

    Raises:
        DocumentFileMissingError: If any expired document is missing its stored file.
    """

    summary = ExpiredDocumentPurgeSummary(dry_run=dry_run)
    settings = config.get_settings()

    iterator = iter_expired_documents(db, batch_size=batch_size, limit=limit)
    if dry_run:
        for batch in iterator:
            for document in batch:
                _ensure_document_file(document, settings=settings)
                summary.record(document)
        return summary

    with db.begin():
        for batch in iterator:
            for document in batch:
                deleted_document = delete_document(
                    db,
                    document.document_id,
                    deleted_by=deleted_by,
                    delete_reason=delete_reason,
                    commit=False,
                    event_actor_type="system",
                    event_actor_label=deleted_by,
                    event_source=event_source,
                    event_request_id=event_request_id,
                )
                summary.record(deleted_document)

    return summary


__all__ = [
    "DocumentNotFoundError",
    "DocumentTooLargeError",
    "DocumentStoragePathError",
    "DocumentFileMissingError",
    "InvalidDocumentExpirationError",
    "store_document",
    "list_documents",
    "get_document",
    "update_document",
    "resolve_document_path",
    "delete_document",
    "iter_document_file",
    "iter_expired_documents",
    "purge_expired_documents",
    "PurgedDocument",
    "ExpiredDocumentPurgeSummary",
]
