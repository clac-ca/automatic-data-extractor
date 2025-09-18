"""Document ingestion and storage helpers.

This module owns the logic that writes uploaded files into the hashed
directory structure under ``var/documents/`` and exposes metadata lookup
utilities for API routes and background jobs. Centralising the behaviour
keeps FastAPI routes small and ensures every entry point deduplicates on
the SHA-256 digest before hitting the filesystem.
"""

from __future__ import annotations

import io
import tempfile
from collections.abc import Iterator
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import Document

_HASH_PREFIX = "sha256:"
_CHUNK_SIZE = 1024 * 1024


class DocumentNotFoundError(Exception):
    """Raised when a document identifier cannot be located."""

    def __init__(self, document_id: str) -> None:
        message = f"Document '{document_id}' was not found"
        super().__init__(message)
        self.document_id = document_id


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


def _hash_to_tempfile(stream: BinaryIO) -> tuple[str, int, Path]:
    hasher = sha256()
    size = 0
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        while True:
            chunk = stream.read(_CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
            tmp.write(chunk)
            size += len(chunk)
    digest = hasher.hexdigest()
    return digest, size, Path(tmp.name)


def _storage_path(documents_dir: Path, digest: str) -> Path:
    subdir = Path(digest[:2]) / digest[2:4]
    return documents_dir / subdir / digest


def _get_by_sha(db: Session, sha_value: str) -> Document | None:
    statement = select(Document).where(Document.sha256 == sha_value).limit(1)
    return db.scalars(statement).first()


def store_document(
    db: Session,
    *,
    original_filename: str | None,
    content_type: str | None,
    data: bytes | BinaryIO,
) -> Document:
    """Persist a document to disk and return the metadata record.

    Uploads deduplicate on the SHA-256 digest. When a file with the same
    digest already exists, the existing record is returned and the incoming
    payload is discarded (unless the original file is missing, in which case
    it is restored).
    """

    stream = _as_stream(data)
    _rewind(stream)

    digest, size, tmp_path = _hash_to_tempfile(stream)
    sha_value = f"{_HASH_PREFIX}{digest}"
    tmp_to_remove: Path | None = tmp_path
    settings = config.get_settings()

    try:
        existing = _get_by_sha(db, sha_value)
        if existing is not None:
            stored_path = resolve_document_path(existing, settings=settings)
            if not stored_path.exists():
                stored_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path.replace(stored_path)
                tmp_to_remove = None
            return existing

        stored_path = _storage_path(settings.documents_dir, digest)
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.replace(stored_path)
        tmp_to_remove = None

        document = Document(
            original_filename=_normalise_filename(original_filename),
            content_type=_normalise_content_type(content_type),
            byte_size=size,
            sha256=sha_value,
            stored_uri=str(stored_path),
            metadata_={},
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
    finally:
        if tmp_to_remove is not None:
            tmp_to_remove.unlink(missing_ok=True)


def list_documents(db: Session) -> list[Document]:
    """Return documents ordered by creation time (newest first)."""

    statement = select(Document).order_by(Document.created_at.desc())
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
    try:
        relative = stored_path.relative_to(settings.documents_dir)
    except ValueError:
        return Path.cwd() / stored_path
    return settings.documents_dir / relative


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
    "store_document",
    "list_documents",
    "get_document",
    "resolve_document_path",
    "iter_document_file",
]
