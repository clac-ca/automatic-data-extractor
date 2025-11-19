"""Service layer for document upload and retrieval."""

from __future__ import annotations

import unicodedata
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.features.jobs.repository import JobsRepository
from ade_api.features.users.models import User
from ade_api.settings import Settings
from ade_api.shared.db import generate_ulid
from ade_api.shared.pagination import paginate_sql
from ade_api.shared.types import OrderBy

from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    InvalidDocumentExpirationError,
)
from .filters import DocumentFilters, DocumentSource, DocumentStatus, apply_document_filters
from .models import Document
from .repository import DocumentsRepository
from .schemas import DocumentLastRun, DocumentOut, DocumentPage
from .storage import DocumentStorage

_FALLBACK_FILENAME = "upload"
_MAX_FILENAME_LENGTH = 255


class DocumentsService:
    """Manage document metadata and backing file storage."""

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

        documents_dir = settings.documents_dir
        if documents_dir is None:
            raise RuntimeError("Document storage directory is not configured")
        self._storage = DocumentStorage(documents_dir)
        self._repository = DocumentsRepository(session)
        self._jobs_repository = JobsRepository(session)

    async def create_document(
        self,
        *,
        workspace_id: str,
        upload: UploadFile,
        metadata: Mapping[str, Any] | None = None,
        expires_at: str | None = None,
        actor: User | None = None,
    ) -> DocumentOut:
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
            attributes=metadata_payload,
            uploaded_by_user_id=cast(str | None, getattr(actor, "id", None)),
            status=DocumentStatus.UPLOADED.value,
            source=DocumentSource.MANUAL_UPLOAD.value,
            expires_at=expiration,
            last_run_at=None,
        )
        self._session.add(document)
        await self._session.flush()
        stmt = self._repository.base_query(workspace_id).where(Document.id == document_id)
        result = await self._session.execute(stmt)
        hydrated = result.scalar_one()

        return DocumentOut.model_validate(hydrated)

    async def list_documents(
        self,
        *,
        workspace_id: str,
        page: int,
        page_size: int,
        include_total: bool,
        order_by: OrderBy,
        filters: DocumentFilters,
        actor: User | None = None,
    ) -> DocumentPage:
        """Return paginated documents with the shared envelope."""

        stmt = (
            self._repository.base_query(workspace_id)
            .where(Document.deleted_at.is_(None))
        )
        stmt = apply_document_filters(stmt, filters, actor=actor)

        page_result = await paginate_sql(
            self._session,
            stmt,
            page=page,
            page_size=page_size,
            order_by=order_by,
            include_total=include_total,
        )
        items = [DocumentOut.model_validate(item) for item in page_result.items]
        await self._attach_last_runs(workspace_id, items)

        return DocumentPage(
            items=items,
            page=page_result.page,
            page_size=page_result.page_size,
            has_next=page_result.has_next,
            has_previous=page_result.has_previous,
            total=page_result.total,
        )

    async def get_document(self, *, workspace_id: str, document_id: str) -> DocumentOut:
        """Return document metadata for ``document_id``."""

        document = await self._get_document(workspace_id, document_id)
        payload = DocumentOut.model_validate(document)
        await self._attach_last_runs(workspace_id, [payload])
        return payload

    async def stream_document(
        self, *, workspace_id: str, document_id: str
    ) -> tuple[DocumentOut, AsyncIterator[bytes]]:
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
            try:
                async for chunk in stream:
                    yield chunk
            except FileNotFoundError as exc:
                raise DocumentFileMissingError(
                    document_id=document_id,
                    stored_uri=document.stored_uri,
                ) from exc

        payload = DocumentOut.model_validate(document)
        await self._attach_last_runs(workspace_id, [payload])
        return payload, _guarded()

    async def delete_document(
        self,
        *,
        workspace_id: str,
        document_id: str,
        actor: User | None = None,
    ) -> None:
        """Soft delete ``document_id`` and remove the stored file."""

        document = await self._get_document(workspace_id, document_id)
        now = datetime.now(tz=UTC)
        document.deleted_at = now
        if actor is not None:
            document.deleted_by_user_id = getattr(actor, "id", None)
        await self._session.flush()

        await self._storage.delete(document.stored_uri)

    async def _get_document(self, workspace_id: str, document_id: str) -> Document:
        document = await self._repository.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        if document is None:
            raise DocumentNotFoundError(document_id)
        return document

    async def _attach_last_runs(
        self,
        workspace_id: str,
        documents: Sequence[DocumentOut],
    ) -> None:
        """Populate ``last_run`` on each document using recent job data."""

        if not documents:
            return

        summaries = await self._jobs_repository.latest_runs_for_documents(
            workspace_id=workspace_id,
            document_ids=[document.id for document in documents],
        )
        for document in documents:
            summary = summaries.get(document.id)
            if summary is None:
                document.last_run = None
                continue

            document.last_run = DocumentLastRun(
                job_id=summary.job_id,
                status=summary.status,
                run_at=summary.run_at,
                message=summary.message,
            )

    def _resolve_expiration(self, override: str | None, now: datetime) -> datetime:
        if override is None:
            expires = now + self._settings.storage_document_retention_period
            return expires

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

        return parsed

    def _normalise_filename(self, name: str | None) -> str:
        """Return a safe, display-friendly filename for stored documents."""

        if name is None:
            return _FALLBACK_FILENAME

        candidate = name.strip()
        if not candidate:
            return _FALLBACK_FILENAME

        # Strip control characters (including newlines) to avoid header injection and
        # other control sequence issues when the filename is rendered in responses.
        filtered = "".join(
            ch for ch in candidate if unicodedata.category(ch)[0] != "C"
        ).strip()

        if not filtered:
            return _FALLBACK_FILENAME

        if len(filtered) > _MAX_FILENAME_LENGTH:
            filtered = filtered[:_MAX_FILENAME_LENGTH].rstrip()

        return filtered or _FALLBACK_FILENAME

    def _normalise_content_type(self, content_type: str | None) -> str | None:
        if content_type is None:
            return None
        candidate = content_type.strip()
        return candidate or None


__all__ = ["DocumentsService"]
