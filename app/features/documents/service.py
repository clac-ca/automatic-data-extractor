"""Service layer for document upload and retrieval."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from typing import Any

from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db import generate_ulid
from app.features.users.models import User

from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    InvalidDocumentExpirationError,
)
from .models import Document
from .schemas import DocumentRecord
from .storage import DocumentStorage


class DocumentsService:
    """Manage document metadata and backing file storage."""

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

        documents_dir = settings.storage_documents_dir
        if documents_dir is None:
            raise RuntimeError("Document storage directory is not configured")
        self._storage = DocumentStorage(documents_dir)

    async def create_document(
        self,
        *,
        workspace_id: str,
        upload: UploadFile,
        metadata: Mapping[str, Any] | None = None,
        expires_at: str | None = None,
        produced_by_job_id: str | None = None,
    ) -> DocumentRecord:
        """Persist ``upload`` to storage and return the resulting metadata record."""

        metadata_payload = dict(metadata or {})
        now = datetime.now(tz=UTC)
        expiration = self._resolve_expiration(expires_at, now)
        document_id = generate_ulid()
        stored_uri = self._storage.make_stored_uri(document_id)

        if upload.file is None:  # pragma: no cover - UploadFile always supplies file
            raise RuntimeError("Upload stream is not available")

        await upload.seek(0)
        stored = await self._storage.write(
            stored_uri,
            upload.file,
            max_bytes=self._settings.storage_upload_max_bytes,
        )

        document = Document(
            id=document_id,
            workspace_id=workspace_id,
            original_filename=self._normalise_filename(upload.filename),
            content_type=self._normalise_content_type(upload.content_type),
            byte_size=stored.byte_size,
            sha256=stored.sha256,
            stored_uri=stored_uri,
            metadata_=metadata_payload,
            expires_at=expiration,
            produced_by_job_id=produced_by_job_id,
        )
        self._session.add(document)
        await self._session.flush()

        return DocumentRecord.model_validate(document)

    async def list_documents(
        self, *, workspace_id: str, limit: int, offset: int
    ) -> list[DocumentRecord]:
        """Return non-deleted documents ordered by recency."""

        stmt = self._base_query(workspace_id).where(Document.deleted_at.is_(None))
        stmt = stmt.order_by(Document.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        documents = result.scalars().all()
        records = [DocumentRecord.model_validate(item) for item in documents]

        return records

    async def get_document(self, *, workspace_id: str, document_id: str) -> DocumentRecord:
        """Return document metadata for ``document_id``."""

        document = await self._get_document(workspace_id, document_id)
        return DocumentRecord.model_validate(document)

    async def stream_document(
        self, *, workspace_id: str, document_id: str
    ) -> tuple[DocumentRecord, AsyncIterator[bytes]]:
        """Return a document record and async iterator for its bytes."""

        document = await self._get_document(workspace_id, document_id)
        path = self._storage.path_for(document.stored_uri)
        exists = await run_in_threadpool(path.exists)
        if not exists:
            raise DocumentFileMissingError(
                document_id=document_id,
                stored_uri=document.stored_uri,
            )

        stream = self._storage.stream(document.stored_uri)

        async def _guarded() -> AsyncIterator[bytes]:
            async for chunk in stream:
                yield chunk

        return DocumentRecord.model_validate(document), _guarded()

    async def delete_document(
        self,
        *,
        workspace_id: str,
        document_id: str,
        reason: str | None = None,
        actor: User | None = None,
    ) -> None:
        """Soft delete ``document_id`` and remove the stored file."""

        document = await self._get_document(workspace_id, document_id)
        now = datetime.now(tz=UTC).isoformat(timespec="seconds")
        document.deleted_at = now
        if actor is not None:
            document.deleted_by = getattr(actor, "id", None)
        document.delete_reason = reason
        await self._session.flush()

        await self._storage.delete(document.stored_uri)

    async def _get_document(self, workspace_id: str, document_id: str) -> Document:
        stmt = self._base_query(workspace_id).where(
            Document.id == document_id,
            Document.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        document = result.scalar_one_or_none()
        if document is None:
            raise DocumentNotFoundError(document_id)
        return document

    def _base_query(self, workspace_id: str) -> Select[tuple[Document]]:
        return select(Document).where(Document.workspace_id == workspace_id)

    def _resolve_expiration(self, override: str | None, now: datetime) -> str:
        if override is None:
            expires = now + self._settings.storage_document_retention_period
            return expires.isoformat(timespec="seconds")

        candidate = override.strip()
        if not candidate:
            raise InvalidDocumentExpirationError("expires_at must not be blank")

        if candidate.endswith(("z", "Z")):
            candidate = f"{candidate[:-1]}+00:00"

        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise InvalidDocumentExpirationError(
                "expires_at must be a valid ISO 8601 timestamp"
            ) from exc

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = parsed.astimezone(UTC)

        if parsed <= now:
            raise InvalidDocumentExpirationError("expires_at must be in the future")

        return parsed.isoformat(timespec="seconds")

    def _normalise_filename(self, name: str | None) -> str:
        if name is None:
            return "upload"
        candidate = name.strip()
        return candidate or "upload"

    def _normalise_content_type(self, content_type: str | None) -> str | None:
        if content_type is None:
            return None
        candidate = content_type.strip()
        return candidate or None


__all__ = ["DocumentsService"]
