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
import logging
import secrets
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, BinaryIO

from sqlalchemy import select, tuple_
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
            for chunk in iter(lambda: stream.read(_CHUNK_SIZE), b""):
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

    Every upload is assigned a unique on-disk location under the configured
    documents directory. The stored file path is randomised so callers do not
    need to coordinate file names ahead of time.
    """

    settings = config.get_settings()
    stream = _prepare_stream(data)

    allocation = _allocate_storage_path(settings.documents_dir)
    digest, size = _persist_stream(
        stream, allocation.disk_path, max_bytes=settings.max_upload_bytes
    )
    sha_value = f"{_HASH_PREFIX}{digest}"
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
                "disk_path": str(allocation.disk_path),
            },
        )
        try:
            allocation.disk_path.unlink(missing_ok=True)
        except Exception:
            logger.exception(
                "Failed to remove stored file after database error",
                extra={
                    "stored_uri": stored_uri,
                    "disk_path": str(allocation.disk_path),
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


def resolve_document_path(
    document: Document, *, settings: config.Settings | None = None
) -> Path:
    """Return the on-disk path for the stored document."""

    settings = settings or config.get_settings()
    stored_uri = (document.stored_uri or "").strip()
    if not stored_uri:
        raise DocumentStoragePathError(document.stored_uri or "")

    base_dir = settings.documents_dir.resolve()
    candidate = Path(stored_uri)
    if not candidate.is_absolute():
        candidate = (base_dir / candidate).resolve()
    else:
        candidate = candidate.resolve()

    try:
        candidate.relative_to(base_dir)
    except ValueError as exc:
        raise DocumentStoragePathError(document.stored_uri) from exc

    return candidate


def _safe_document_path(
    document: Document,
    *,
    settings: config.Settings,
    context: str | None = None,
) -> Path | None:
    """Resolve a document path, logging and returning ``None`` on failure."""

    try:
        return resolve_document_path(document, settings=settings)
    except DocumentStoragePathError as exc:
        message = "Stored URI for document resolves outside documents directory"
        if context:
            message = f"{message} {context}"
        logger.warning(
            message,
            extra={
                "document_id": document.document_id,
                "stored_uri": document.stored_uri,
            },
            exc_info=exc,
        )
        return None


@dataclass(slots=True)
class DocumentDeletionResult:
    """Outcome of a document deletion attempt."""

    document: Document
    missing_before_delete: bool


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
) -> DocumentDeletionResult:
    """Soft delete a document and remove the stored file when present."""

    document = get_document(db, document_id)
    now = datetime.now(timezone.utc)
    settings = config.get_settings()
    path = _safe_document_path(document, settings=settings)
    missing_before_delete = True
    if path is not None:
        missing_before_delete = not path.exists()

    mutated = document.deleted_at is None
    if mutated:
        now_iso = now.isoformat()
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
            path.unlink(missing_ok=True)
        except Exception:
            logger.exception(
                "Failed to remove stored bytes for document deletion",
                extra={
                    "document_id": document.document_id,
                    "stored_uri": document.stored_uri,
                },
            )

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
            record_event(db, event, commit=commit)
        except Exception:
            logger.exception(
                "Failed to record document deletion audit event",
                extra={
                    "document_id": document.document_id,
                    "event_type": "document.deleted",
                    "source": audit_source,
                },
            )

    return DocumentDeletionResult(
        document=document, missing_before_delete=missing_before_delete
    )


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

    def record(self, document: Document, *, missing_before_delete: bool) -> None:
        self.processed_count += 1
        if missing_before_delete:
            self.missing_files += 1
        else:
            self.bytes_reclaimed += document.byte_size

        self.documents.append(
            PurgedDocument(
                document_id=document.document_id,
                stored_uri=document.stored_uri,
                expires_at=document.expires_at,
                byte_size=document.byte_size,
                missing_before_delete=missing_before_delete,
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

    base_query = (
        select(Document)
        .where(Document.deleted_at.is_(None), Document.expires_at <= now_iso)
        .order_by(Document.expires_at.asc(), Document.document_id.asc())
    )

    yielded = 0
    cursor: tuple[str, str] | None = None

    while True:
        remaining = None if limit is None else limit - yielded
        if remaining is not None and remaining <= 0:
            break

        page_size = batch_size if remaining is None else min(batch_size, remaining)
        statement = base_query.limit(page_size)
        if cursor is not None:
            statement = statement.where(
                tuple_(Document.expires_at, Document.document_id) > cursor
            )

        batch = list(db.scalars(statement))
        if not batch:
            break

        yield batch

        yielded += len(batch)
        last = batch[-1]
        cursor = (last.expires_at, last.document_id)


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

    def _missing_before_delete(document: Document) -> bool:
        path = _safe_document_path(
            document,
            settings=settings,
            context="during purge",
        )
        if path is None:
            return True
        return not path.exists()

    iterator = iter_expired_documents(db, batch_size=batch_size, limit=limit)
    if dry_run:
        for batch in iterator:
            for document in batch:
                summary.record(
                    document,
                    missing_before_delete=_missing_before_delete(document),
                )
        return summary

    with db.begin():
        for batch in iterator:
            for document in batch:
                result = delete_document(
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
                summary.record(
                    result.document,
                    missing_before_delete=result.missing_before_delete,
                )

    return summary


__all__ = [
    "DocumentNotFoundError",
    "DocumentTooLargeError",
    "DocumentStoragePathError",
    "InvalidDocumentExpirationError",
    "store_document",
    "list_documents",
    "get_document",
    "resolve_document_path",
    "delete_document",
    "DocumentDeletionResult",
    "iter_document_file",
    "iter_expired_documents",
    "purge_expired_documents",
    "PurgedDocument",
    "ExpiredDocumentPurgeSummary",
]
