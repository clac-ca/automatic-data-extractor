"""Service layer for document upload and retrieval."""

from __future__ import annotations

import unicodedata
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import Select, func, literal, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from apps.api.app.features.users.models import User
from apps.api.app.settings import Settings
from apps.api.app.shared.core.pagination import paginate
from apps.api.app.shared.db import generate_ulid

from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    InvalidDocumentExpirationError,
)
from .filtering import (
    DocumentFilters,
    DocumentSort,
    DocumentSortableField,
    DocumentSource,
    DocumentStatus,
)
from .models import Document, DocumentTag
from .repository import DocumentsRepository
from .schemas import DocumentListResponse, DocumentRecord
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

    async def create_document(
        self,
        *,
        workspace_id: str,
        upload: UploadFile,
        metadata: Mapping[str, Any] | None = None,
        expires_at: str | None = None,
        actor: User | None = None,
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

        return DocumentRecord.model_validate(hydrated)

    async def list_documents(
        self,
        *,
        workspace_id: str,
        page: int,
        per_page: int,
        include_total: bool = False,
        filters: DocumentFilters | None = None,
        sort: DocumentSort | None = None,
        actor: User | None = None,
    ) -> DocumentListResponse:
        """Return paginated documents ordered by recency."""

        filters = filters or DocumentFilters()
        sort = sort or DocumentSort.parse(None)

        stmt = self._repository.base_query(workspace_id).where(Document.deleted_at.is_(None))
        stmt = self._apply_filters(
            stmt,
            filters=filters,
            actor=actor,
        )
        envelope = await paginate(
            self._session,
            stmt,
            page=page,
            per_page=per_page,
            order_by=self._resolve_ordering(sort),
            include_total=include_total,
        )
        envelope["items"] = [
            DocumentRecord.model_validate(item) for item in envelope["items"]
        ]

        return DocumentListResponse.model_validate(envelope)

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

    def _apply_filters(
        self,
        stmt: Select[tuple[Document]],
        *,
        filters: DocumentFilters,
        actor: User | None,
    ) -> Select[tuple[Document]]:
        conditions = []

        if filters.status:
            conditions.append(Document.status.in_([status.value for status in filters.status]))
        if filters.source:
            conditions.append(Document.source.in_([source.value for source in filters.source]))
        if filters.tags:
            conditions.append(Document.tags.any(DocumentTag.tag.in_(filters.tags)))

        uploader_checks: list[str] = []
        if filters.uploader_me:
            if actor is None:
                raise RuntimeError("uploader=me requires an authenticated actor")
            uploader_checks.append(actor.id)
        if filters.uploader_ids:
            uploader_checks.extend(filters.uploader_ids)
        if uploader_checks:
            conditions.append(Document.uploaded_by_user_id.in_(uploader_checks))

        if filters.created_from is not None:
            conditions.append(Document.created_at >= filters.created_from)
        if filters.created_to is not None:
            conditions.append(Document.created_at <= filters.created_to)

        if filters.last_run_from is not None:
            conditions.append(Document.last_run_at.is_not(None))
            conditions.append(Document.last_run_at >= filters.last_run_from)
        if filters.last_run_to is not None:
            conditions.append(
                or_(Document.last_run_at <= filters.last_run_to, Document.last_run_at.is_(None))
            )

        if filters.byte_size_min is not None:
            conditions.append(Document.byte_size >= filters.byte_size_min)
        if filters.byte_size_max is not None:
            conditions.append(Document.byte_size <= filters.byte_size_max)

        if filters.q:
            uploader_alias = aliased(User)
            pattern = f"%{filters.q}%"
            lowered_pattern = func.lower(literal(pattern))
            stmt = stmt.outerjoin(uploader_alias, Document.uploaded_by_user)
            conditions.append(
                or_(
                    func.lower(Document.original_filename).like(lowered_pattern),
                    func.lower(uploader_alias.display_name).like(lowered_pattern),
                    func.lower(uploader_alias.email).like(lowered_pattern),
                )
            )

        if conditions:
            stmt = stmt.where(*conditions)

        return stmt

    def _resolve_ordering(self, sort: DocumentSort) -> tuple[object, ...]:
        column_map = {
            DocumentSortableField.CREATED_AT: Document.created_at,
            DocumentSortableField.STATUS: Document.status,
            DocumentSortableField.LAST_RUN_AT: Document.last_run_at,
            DocumentSortableField.BYTE_SIZE: Document.byte_size,
            DocumentSortableField.SOURCE: Document.source,
            DocumentSortableField.NAME: Document.original_filename,
        }

        column = column_map[sort.field]
        if sort.field is DocumentSortableField.NAME:
            ordered_column = func.lower(column)
        else:
            ordered_column = column

        direction = (
            ordered_column.desc() if sort.descending else ordered_column.asc()
        )

        order_parts: list[object] = []
        if sort.field is DocumentSortableField.LAST_RUN_AT:
            order_parts.append(Document.last_run_at.is_(None))
            direction = (
                column.desc() if sort.descending else column.asc()
            )

        order_parts.append(direction)
        order_parts.append(Document.id.desc())

        return tuple(order_parts)

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
