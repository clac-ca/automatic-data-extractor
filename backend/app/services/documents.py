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
import logging
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
from .audit_log import AuditEventRecord, record_event

_HASH_PREFIX = "sha256:"
_CHUNK_SIZE = 1024 * 1024
_MAX_STORAGE_KEY_ATTEMPTS = 10


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


def _prepare_stream(data: bytes | BinaryIO) -> BinaryIO:
    """Return a binary stream positioned at the start of the payload."""

    stream = io.BytesIO(data) if isinstance(data, (bytes, bytearray)) else data
    try:
        if hasattr(stream, "seek") and stream.seekable():
            stream.seek(0)
    except Exception:  # pragma: no cover - defensive fallback
        pass
    return stream


def _generate_storage_token() -> str:
    return secrets.token_hex(32)


def _relative_storage_path(token: str) -> Path:
    return Path(token[:2]) / token[2:4] / token


@dataclass(frozen=True)
class _StorageAllocation:
    """Allocated location for a document on disk."""

    relative_path: Path
    disk_path: Path

    @property
    def uri(self) -> str:
        return self.relative_path.as_posix()


def _allocate_storage_path(documents_dir: Path) -> _StorageAllocation:
    for _ in range(_MAX_STORAGE_KEY_ATTEMPTS):
        token = _generate_storage_token()
        relative = _relative_storage_path(token)
        disk_path = documents_dir / relative
        if not disk_path.exists():
            return _StorageAllocation(relative, disk_path)
    raise RuntimeError("Unable to allocate unique storage path")


@dataclass(frozen=True)
class _PersistedStream:
    """Details about a stream that has been written to disk."""

    digest: str
    size: int


def _persist_stream(
    stream: BinaryIO,
    destination: Path,
    *,
    max_bytes: int | None = None,
) -> _PersistedStream:
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
                    # Validate the limit before touching the filesystem so we
                    # never leave a partially written payload behind.
                    raise DocumentTooLargeError(
                        limit=max_bytes, received=prospective_size
                    )
                target.write(chunk)
                hasher.update(chunk)
                size = prospective_size
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return _PersistedStream(digest=hasher.hexdigest(), size=size)


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
    stream = _prepare_stream(data)

    allocation = _allocate_storage_path(settings.documents_dir)
    persisted = _persist_stream(
        stream, allocation.disk_path, max_bytes=settings.max_upload_bytes
    )
    sha_value = f"{_HASH_PREFIX}{persisted.digest}"
    stored_uri = allocation.uri

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
        byte_size=persisted.size,
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
    commit: bool = True,
    audit_actor_type: str | None = None,
    audit_actor_id: str | None = None,
    audit_actor_label: str | None = None,
    audit_source: str | None = None,
    audit_request_id: str | None = None,
    audit_payload: dict[str, Any] | None = None,
) -> Document:
    """Soft delete a document and remove the stored file when present."""

    document = get_document(db, document_id)
    now = datetime.now(timezone.utc)
    settings = config.get_settings()
    path = resolve_document_path(document, settings=settings)
    missing_before_delete = not path.exists()
    path.unlink(missing_ok=True)

    mutated = False
    if document.deleted_at is None:
        now_iso = now.isoformat()
        document.deleted_at = now_iso
        document.deleted_by = deleted_by
        document.delete_reason = delete_reason
        document.updated_at = now_iso
        db.add(document)
        mutated = True

    if commit:
        db.commit()
        if mutated:
            db.refresh(document)
    elif mutated:
        db.flush()

    if mutated:
        payload: dict[str, Any] = {
            "deleted_by": document.deleted_by,
            "delete_reason": document.delete_reason,
            "byte_size": document.byte_size,
            "stored_uri": document.stored_uri,
            "sha256": document.sha256,
            "expires_at": document.expires_at,
            "missing_before_delete": missing_before_delete,
        }
        if audit_payload:
            payload.update(audit_payload)

        event = AuditEventRecord(
            event_type="document.deleted",
            entity_type="document",
            entity_id=document.document_id,
            actor_type=audit_actor_type,
            actor_id=audit_actor_id,
            actor_label=audit_actor_label or document.deleted_by,
            source=audit_source,
            request_id=audit_request_id,
            occurred_at=document.deleted_at,
            payload=payload,
        )

        try:
            if commit:
                record_event(db, event, commit=True)
            else:
                with db.begin_nested():
                    record_event(db, event, commit=False)
        except Exception:
            logger.exception(
                "Failed to record document deletion audit event",
                extra={
                    "document_id": document.document_id,
                    "event_type": "document.deleted",
                    "source": audit_source,
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
    missing_before_delete: bool


@dataclass(slots=True)
class ExpiredDocumentPurgeSummary:
    """Aggregated outcome of a purge run."""

    dry_run: bool
    processed_count: int = 0
    missing_files: int = 0
    bytes_reclaimed: int = 0
    documents: list[PurgedDocument] = field(default_factory=list)


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
    id_statement = (
        select(Document.document_id)
        .where(Document.deleted_at.is_(None), Document.expires_at <= now_iso)
        .order_by(Document.expires_at.asc(), Document.document_id.asc())
    )
    if limit is not None:
        if limit <= 0:
            return
        id_statement = id_statement.limit(limit)

    document_ids = list(db.scalars(id_statement))
    for start in range(0, len(document_ids), batch_size):
        chunk_ids = document_ids[start : start + batch_size]
        documents = db.scalars(
            select(Document).where(Document.document_id.in_(chunk_ids))
        ).all()
        document_map = {document.document_id: document for document in documents}
        batch = [document_map[doc_id] for doc_id in chunk_ids if doc_id in document_map]
        if batch:
            yield batch


def purge_expired_documents(
    db: Session,
    *,
    limit: int | None = None,
    dry_run: bool = False,
    batch_size: int = 100,
    deleted_by: str = "maintenance:purge_expired_documents",
    delete_reason: str = "expired_document_purge",
    audit_source: str = "scheduler",
    audit_request_id: str | None = None,
) -> ExpiredDocumentPurgeSummary:
    """Remove expired documents and mark their metadata."""

    summary = ExpiredDocumentPurgeSummary(dry_run=dry_run)
    settings = config.get_settings()

    def _process(document: Document) -> None:
        path = resolve_document_path(document, settings=settings)
        missing_before_delete = not path.exists()
        summary.processed_count += 1
        if missing_before_delete:
            summary.missing_files += 1
        else:
            summary.bytes_reclaimed += document.byte_size

        summary.documents.append(
            PurgedDocument(
                document_id=document.document_id,
                stored_uri=document.stored_uri,
                expires_at=document.expires_at,
                byte_size=document.byte_size,
                missing_before_delete=missing_before_delete,
            )
        )

        if dry_run:
            return

        delete_document(
            db,
            document.document_id,
            deleted_by=deleted_by,
            delete_reason=delete_reason,
            commit=False,
            audit_actor_type="system",
            audit_actor_label=deleted_by,
            audit_source=audit_source,
            audit_request_id=audit_request_id,
        )

    iterator = iter_expired_documents(db, batch_size=batch_size, limit=limit)
    if dry_run:
        for batch in iterator:
            for document in batch:
                _process(document)
        return summary

    with db.begin():
        for batch in iterator:
            for document in batch:
                _process(document)

    return summary


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
    "iter_expired_documents",
    "purge_expired_documents",
    "PurgedDocument",
    "ExpiredDocumentPurgeSummary",
]
