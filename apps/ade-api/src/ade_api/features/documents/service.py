"""Service layer for document upload and retrieval."""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID

import openpyxl
from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.ids import generate_uuid7
from ade_api.common.logging import log_context
from ade_api.common.pagination import paginate_sql
from ade_api.common.time import utc_now
from ade_api.common.types import OrderBy
from ade_api.infra.storage import workspace_documents_root
from ade_api.models import (
    Document,
    DocumentChange,
    DocumentSource,
    DocumentStatus,
    DocumentTag,
    DocumentChangeType,
    DocumentUploadSession,
    DocumentUploadSessionStatus,
    Run,
    RunStatus,
    User,
    Workspace,
)
from ade_api.settings import Settings

from .change_feed import DocumentChangesService
from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentTooLargeError,
    DocumentUploadRangeError,
    DocumentUploadSessionExpiredError,
    DocumentUploadSessionNotFoundError,
    DocumentUploadSessionNotReadyError,
    DocumentWorksheetParseError,
    InvalidDocumentExpirationError,
    InvalidDocumentTagsError,
)
from .filters import DocumentFilters, apply_document_filters
from .schemas import DocumentUploadRunOptions
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.features.runs.repository import RunsRepository
from ade_api.features.workspaces.repository import WorkspacesRepository
from ade_api.features.workspaces.settings import read_processing_paused

from .repository import DocumentsRepository
from .schemas import (
    DocumentChangeEntry,
    DocumentChangesPage,
    DocumentLastRun,
    DocumentDisplayStatus,
    DocumentQueueReason,
    DocumentQueueState,
    DocumentOut,
    DocumentPage,
    DocumentSheet,
    DocumentUpdateRequest,
    DocumentUploadSessionCreateRequest,
    DocumentUploadSessionCreateResponse,
    DocumentUploadSessionStatusResponse,
    DocumentUploadSessionUploadResponse,
    TagCatalogItem,
    TagCatalogPage,
)
from .storage import DocumentStorage
from .tags import (
    MAX_TAGS_PER_DOCUMENT,
    TagValidationError,
    normalize_tag_list,
    normalize_tag_query,
)

logger = logging.getLogger(__name__)

UPLOAD_RUN_OPTIONS_KEY = "__ade_run_options"

_FALLBACK_FILENAME = "upload"
_MAX_FILENAME_LENGTH = 255
_UPLOAD_SESSION_PREFIX = "upload_sessions"
_CONTENT_RANGE_PATTERN = re.compile(r"^bytes (\d+)-(\d+)/(\d+)$")


@dataclass(slots=True)
class DocumentQueueContext:
    has_active_configuration: bool
    queue_has_capacity: bool
    processing_paused: bool


class DocumentsService:
    """Manage document metadata and backing file storage."""

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

        documents_dir = settings.documents_dir
        if documents_dir is None:
            raise RuntimeError("Document storage directory is not configured")

        self._repository = DocumentsRepository(session)
        self._changes = DocumentChangesService(session=session, settings=settings)
        self._configs = ConfigurationsRepository(session)
        self._runs = RunsRepository(session)
        self._workspaces = WorkspacesRepository(session)

    @staticmethod
    def build_upload_metadata(
        metadata: Mapping[str, Any] | None,
        run_options: DocumentUploadRunOptions | None,
    ) -> dict[str, Any]:
        payload = dict(metadata or {})
        if run_options is not None:
            payload[UPLOAD_RUN_OPTIONS_KEY] = run_options.model_dump(exclude_none=True)
        return payload

    @staticmethod
    def read_upload_run_options(
        metadata: Mapping[str, Any] | None,
    ) -> DocumentUploadRunOptions | None:
        if not metadata:
            return None
        raw = metadata.get(UPLOAD_RUN_OPTIONS_KEY)
        if raw is None:
            return None
        try:
            return DocumentUploadRunOptions.model_validate(raw)
        except ValidationError:
            return None

    async def create_document(
        self,
        *,
        workspace_id: UUID,
        upload: UploadFile,
        metadata: Mapping[str, Any] | None = None,
        expires_at: str | None = None,
        actor: User | None = None,
    ) -> DocumentOut:
        """Persist ``upload`` to storage and return the resulting metadata record."""

        actor_id: UUID | None = actor.id if actor is not None else None
        logger.debug(
            "document.create.start",
            extra=log_context(
                workspace_id=workspace_id,
                user_id=actor_id,
                upload_filename=upload.filename,
                content_type=upload.content_type,
                expires_at=expires_at,
            ),
        )

        metadata_payload = dict(metadata or {})
        now = datetime.now(tz=UTC)
        expiration = self._resolve_expiration(expires_at, now)
        document_id = generate_uuid7()
        storage = self._storage_for(workspace_id)
        stored_uri = storage.make_stored_uri(str(document_id))

        if upload.file is None:  # pragma: no cover - UploadFile always supplies file
            raise RuntimeError("Upload stream is not available")

        await upload.seek(0)
        stored = await storage.write(
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
            uploaded_by_user_id=actor_id,
            status=DocumentStatus.UPLOADED,
            source=DocumentSource.MANUAL_UPLOAD,
            expires_at=expiration,
            last_run_at=None,
        )
        self._session.add(document)
        await self._session.flush()

        stmt = self._repository.base_query(workspace_id).where(Document.id == document_id)
        result = await self._session.execute(stmt)
        hydrated = result.scalar_one()

        payload = DocumentOut.model_validate(hydrated)
        queue_context = await self.build_queue_context(workspace_id=workspace_id)
        self._apply_derived_fields(payload, queue_context)
        await self._changes.record_upsert(
            workspace_id=workspace_id,
            document_id=document_id,
            payload=payload.model_dump(),
        )

        logger.info(
            "document.create.success",
            extra=log_context(
                workspace_id=workspace_id,
                document_id=document_id,
                user_id=actor_id,
                content_type=document.content_type,
                byte_size=document.byte_size,
                expires_at=document.expires_at.isoformat() if document.expires_at else None,
            ),
        )

        return payload

    async def list_documents(
        self,
        *,
        workspace_id: UUID,
        page: int,
        page_size: int,
        include_total: bool,
        order_by: OrderBy,
        filters: DocumentFilters,
        actor: User | None = None,
    ) -> DocumentPage:
        """Return paginated documents with the shared envelope."""

        actor_id: UUID | None = actor.id if actor is not None else None
        logger.debug(
            "document.list.start",
            extra=log_context(
                workspace_id=workspace_id,
                user_id=actor_id,
                page=page,
                page_size=page_size,
                include_total=include_total,
                order_by=str(order_by),
            ),
        )

        stmt = self._repository.base_query(workspace_id).where(Document.deleted_at.is_(None))
        stmt = apply_document_filters(stmt, filters, actor=actor)

        # Capture the cursor before listing to avoid skipping changes committed during the query.
        changes_cursor = await self._changes.current_cursor(workspace_id=workspace_id)
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
        queue_context = await self.build_queue_context(workspace_id=workspace_id)
        for item in items:
            self._apply_derived_fields(item, queue_context)

        logger.info(
            "document.list.success",
            extra=log_context(
                workspace_id=workspace_id,
                user_id=actor_id,
                page=page_result.page,
                page_size=page_result.page_size,
                count=len(items),
                has_next=page_result.has_next,
                has_previous=page_result.has_previous,
                total=page_result.total if include_total else None,
            ),
        )

        return DocumentPage(
            items=items,
            page=page_result.page,
            page_size=page_result.page_size,
            has_next=page_result.has_next,
            has_previous=page_result.has_previous,
            total=page_result.total,
            changes_cursor=str(changes_cursor),
        )

    async def list_document_changes(
        self,
        *,
        workspace_id: UUID,
        cursor_token: str,
        limit: int,
    ) -> DocumentChangesPage:
        if cursor_token == "latest":
            latest = await self._changes.current_cursor(workspace_id=workspace_id)
            return DocumentChangesPage(changes=[], next_cursor=str(latest))

        try:
            cursor = int(cursor_token)
        except (TypeError, ValueError) as exc:
            raise ValueError("cursor must be an integer string or 'latest'") from exc

        page = await self._changes.list_changes(
            workspace_id=workspace_id,
            cursor=cursor,
            limit=limit,
        )
        queue_context = await self.build_queue_context(workspace_id=workspace_id)
        entries = [self._serialize_change(change, queue_context) for change in page.changes]
        return DocumentChangesPage(changes=entries, next_cursor=str(page.next_cursor))

    async def create_upload_session(
        self,
        *,
        workspace_id: UUID,
        payload: DocumentUploadSessionCreateRequest,
        actor: User | None,
    ) -> DocumentUploadSessionCreateResponse:
        if payload.byte_size > self._settings.storage_upload_max_bytes:
            raise DocumentTooLargeError(
                limit=self._settings.storage_upload_max_bytes,
                received=payload.byte_size,
            )

        now = utc_now()
        expires_at = now + self._settings.documents_upload_session_ttl
        session_id = generate_uuid7()
        storage = self._upload_session_storage(workspace_id)
        stored_uri = storage.make_stored_uri(str(session_id))

        session = DocumentUploadSession(
            id=session_id,
            workspace_id=workspace_id,
            created_by_user_id=actor.id if actor else None,
            filename=payload.filename,
            content_type=payload.content_type,
            byte_size=payload.byte_size,
            upload_metadata=self.build_upload_metadata(payload.metadata, payload.run_options),
            conflict_behavior=payload.conflict_behavior,
            folder_id=payload.folder_id,
            temp_stored_uri=stored_uri,
            received_bytes=0,
            received_ranges=["0-"],
            status=DocumentUploadSessionStatus.ACTIVE,
            expires_at=expires_at,
        )
        self._session.add(session)
        await self._session.flush()

        return DocumentUploadSessionCreateResponse(
            upload_session_id=str(session_id),
            expires_at=expires_at,
            chunk_size_bytes=self._settings.documents_upload_session_chunk_bytes,
            next_expected_ranges=self._next_expected_ranges(session),
            upload_url=f"/workspaces/{workspace_id}/documents/uploadSessions/{session_id}",
        )

    async def upload_session_range(
        self,
        *,
        workspace_id: UUID,
        upload_session_id: UUID,
        content_range: str | None,
        body: AsyncIterator[bytes],
    ) -> DocumentUploadSessionUploadResponse:
        session = await self._require_upload_session(
            workspace_id=workspace_id,
            upload_session_id=upload_session_id,
        )
        expected_ranges = self._next_expected_ranges(session)
        if content_range is None:
            raise DocumentUploadRangeError(
                "Content-Range header is required",
                next_expected_ranges=expected_ranges,
            )

        try:
            start, end, total = self._parse_content_range(content_range)
        except ValueError as exc:
            raise DocumentUploadRangeError(
                str(exc),
                next_expected_ranges=expected_ranges,
            ) from exc
        if total != session.byte_size:
            raise DocumentUploadRangeError(
                "Content-Range total does not match session byte_size",
                next_expected_ranges=expected_ranges,
            )
        if start != session.received_bytes:
            raise DocumentUploadRangeError(
                "Content-Range start does not match next expected byte",
                next_expected_ranges=expected_ranges,
            )

        chunk_size = end - start + 1
        if chunk_size <= 0:
            raise DocumentUploadRangeError(
                "Content-Range specifies an empty range",
                next_expected_ranges=expected_ranges,
            )
        if chunk_size > self._settings.documents_upload_session_chunk_bytes:
            raise DocumentUploadRangeError(
                "Content-Range exceeds chunk size limit",
                next_expected_ranges=expected_ranges,
            )

        await self._write_upload_range(
            session=session,
            start=start,
            expected_size=chunk_size,
            body=body,
        )

        session.received_bytes = end + 1
        if session.received_bytes >= session.byte_size:
            session.status = DocumentUploadSessionStatus.COMPLETE

        session.received_ranges = self._next_expected_ranges(session)
        await self._session.flush()

        return DocumentUploadSessionUploadResponse(
            next_expected_ranges=session.received_ranges,
            upload_complete=session.status == DocumentUploadSessionStatus.COMPLETE,
        )

    async def get_upload_session_status(
        self,
        *,
        workspace_id: UUID,
        upload_session_id: UUID,
    ) -> DocumentUploadSessionStatusResponse:
        session = await self._require_upload_session(
            workspace_id=workspace_id,
            upload_session_id=upload_session_id,
        )
        return DocumentUploadSessionStatusResponse(
            upload_session_id=str(session.id),
            expires_at=session.expires_at,
            byte_size=session.byte_size,
            received_bytes=session.received_bytes,
            next_expected_ranges=self._next_expected_ranges(session),
            upload_complete=session.status == DocumentUploadSessionStatus.COMPLETE,
            status=session.status,
        )

    async def commit_upload_session(
        self,
        *,
        workspace_id: UUID,
        upload_session_id: UUID,
        actor: User | None,
    ) -> tuple[DocumentOut, DocumentUploadRunOptions | None]:
        session = await self._require_upload_session(
            workspace_id=workspace_id,
            upload_session_id=upload_session_id,
        )
        if session.status != DocumentUploadSessionStatus.COMPLETE:
            raise DocumentUploadSessionNotReadyError(upload_session_id)

        now = utc_now()
        document_id = generate_uuid7()
        storage = self._storage_for(workspace_id)
        stored_uri = storage.make_stored_uri(str(document_id))

        temp_path = self._upload_session_storage(workspace_id).path_for(session.temp_stored_uri)
        sha, size = await self._compute_sha256(temp_path)
        if size != session.byte_size:
            raise DocumentUploadSessionNotReadyError(upload_session_id)

        final_path = storage.path_for(stored_uri)
        await run_in_threadpool(final_path.parent.mkdir, parents=True, exist_ok=True)
        await run_in_threadpool(temp_path.replace, final_path)

        run_options = self.read_upload_run_options(session.upload_metadata)
        metadata_payload = dict(session.upload_metadata or {})
        document = Document(
            id=document_id,
            workspace_id=workspace_id,
            original_filename=self._normalise_filename(session.filename),
            content_type=self._normalise_content_type(session.content_type),
            byte_size=size,
            sha256=sha,
            stored_uri=stored_uri,
            attributes=metadata_payload,
            uploaded_by_user_id=actor.id if actor else session.created_by_user_id,
            status=DocumentStatus.UPLOADED,
            source=DocumentSource.MANUAL_UPLOAD,
            expires_at=self._resolve_expiration(None, now),
            last_run_at=None,
        )
        self._session.add(document)

        session.status = DocumentUploadSessionStatus.COMMITTED
        await self._session.flush()

        stmt = self._repository.base_query(workspace_id).where(Document.id == document_id)
        result = await self._session.execute(stmt)
        hydrated = result.scalar_one()

        payload = DocumentOut.model_validate(hydrated)
        queue_context = await self.build_queue_context(workspace_id=workspace_id)
        self._apply_derived_fields(payload, queue_context)
        await self._changes.record_upsert(
            workspace_id=workspace_id,
            document_id=document_id,
            payload=payload.model_dump(),
        )
        return payload, run_options

    async def cancel_upload_session(
        self,
        *,
        workspace_id: UUID,
        upload_session_id: UUID,
    ) -> None:
        session = await self._require_upload_session(
            workspace_id=workspace_id,
            upload_session_id=upload_session_id,
        )
        storage = self._upload_session_storage(workspace_id)
        await storage.delete(session.temp_stored_uri)
        await self._session.delete(session)

    async def get_document(self, *, workspace_id: UUID, document_id: UUID) -> DocumentOut:
        """Return document metadata for ``document_id``."""

        logger.debug(
            "document.get.start",
            extra=log_context(workspace_id=workspace_id, document_id=document_id),
        )
        document = await self._get_document(workspace_id, document_id)
        payload = DocumentOut.model_validate(document)
        await self._attach_last_runs(workspace_id, [payload])
        queue_context = await self.build_queue_context(workspace_id=workspace_id)
        self._apply_derived_fields(payload, queue_context)

        logger.info(
            "document.get.success",
            extra=log_context(
                workspace_id=workspace_id,
                document_id=document_id,
                status=document.status,
                byte_size=document.byte_size,
            ),
        )
        return payload

    async def update_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        payload: DocumentUpdateRequest,
    ) -> DocumentOut:
        document = await self._get_document(workspace_id, document_id)

        if "assignee_user_id" in payload.model_fields_set:
            document.assignee_user_id = payload.assignee_user_id
        if "metadata" in payload.model_fields_set and payload.metadata is not None:
            document.attributes = dict(payload.metadata)

        await self._session.flush()

        updated = DocumentOut.model_validate(document)
        queue_context = await self.build_queue_context(workspace_id=workspace_id)
        self._apply_derived_fields(updated, queue_context)
        await self._changes.record_upsert(
            workspace_id=workspace_id,
            document_id=document_id,
            payload=updated.model_dump(),
        )
        return updated

    async def archive_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> DocumentOut:
        """Archive a document to remove it from active workflows."""

        document = await self._get_document(workspace_id, document_id)
        changed = document.status != DocumentStatus.ARCHIVED
        if changed:
            document.status = DocumentStatus.ARCHIVED
            await self._session.flush()

        payload = DocumentOut.model_validate(document)
        queue_context = await self.build_queue_context(workspace_id=workspace_id)
        self._apply_derived_fields(payload, queue_context)
        if changed:
            await self._changes.record_upsert(
                workspace_id=workspace_id,
                document_id=document_id,
                payload=payload.model_dump(),
            )
        return payload

    async def archive_documents_batch(
        self,
        *,
        workspace_id: UUID,
        document_ids: Sequence[UUID],
    ) -> list[DocumentOut]:
        """Archive multiple documents."""

        ordered_ids = list(dict.fromkeys(document_ids))
        if not ordered_ids:
            return []

        documents = await self._require_documents(
            workspace_id=workspace_id,
            document_ids=ordered_ids,
        )
        document_by_id = {doc.id: doc for doc in documents}
        changed_ids: set[UUID] = set()

        for document in documents:
            if document.status == DocumentStatus.ARCHIVED:
                continue
            document.status = DocumentStatus.ARCHIVED
            changed_ids.add(document.id)

        if changed_ids:
            await self._session.flush()

        queue_context = await self.build_queue_context(workspace_id=workspace_id)
        payloads: list[DocumentOut] = []
        for doc_id in ordered_ids:
            payload = DocumentOut.model_validate(document_by_id[doc_id])
            self._apply_derived_fields(payload, queue_context)
            payloads.append(payload)
            if doc_id in changed_ids:
                await self._changes.record_upsert(
                    workspace_id=workspace_id,
                    document_id=doc_id,
                    payload=payload.model_dump(),
                )

        return payloads

    async def restore_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> DocumentOut:
        """Restore a document from the archive."""

        document = await self._get_document(workspace_id, document_id)
        if document.status != DocumentStatus.ARCHIVED:
            payload = DocumentOut.model_validate(document)
            queue_context = await self.build_queue_context(workspace_id=workspace_id)
            self._apply_derived_fields(payload, queue_context)
            return payload

        status_map = await self._latest_run_statuses(
            workspace_id=workspace_id,
            document_ids=[document.id],
        )
        document.status = self._status_from_last_run(status_map.get(document.id))
        await self._session.flush()

        payload = DocumentOut.model_validate(document)
        queue_context = await self.build_queue_context(workspace_id=workspace_id)
        self._apply_derived_fields(payload, queue_context)
        await self._changes.record_upsert(
            workspace_id=workspace_id,
            document_id=document_id,
            payload=payload.model_dump(),
        )
        return payload

    async def restore_documents_batch(
        self,
        *,
        workspace_id: UUID,
        document_ids: Sequence[UUID],
    ) -> list[DocumentOut]:
        """Restore multiple documents from the archive."""

        ordered_ids = list(dict.fromkeys(document_ids))
        if not ordered_ids:
            return []

        documents = await self._require_documents(
            workspace_id=workspace_id,
            document_ids=ordered_ids,
        )
        document_by_id = {doc.id: doc for doc in documents}
        status_map = await self._latest_run_statuses(
            workspace_id=workspace_id,
            document_ids=list(document_by_id.keys()),
        )
        changed_ids: set[UUID] = set()

        for document in documents:
            if document.status != DocumentStatus.ARCHIVED:
                continue
            document.status = self._status_from_last_run(status_map.get(document.id))
            changed_ids.add(document.id)

        if changed_ids:
            await self._session.flush()

        queue_context = await self.build_queue_context(workspace_id=workspace_id)
        payloads: list[DocumentOut] = []
        for doc_id in ordered_ids:
            payload = DocumentOut.model_validate(document_by_id[doc_id])
            self._apply_derived_fields(payload, queue_context)
            payloads.append(payload)
            if doc_id in changed_ids:
                await self._changes.record_upsert(
                    workspace_id=workspace_id,
                    document_id=doc_id,
                    payload=payload.model_dump(),
                )

        return payloads

    async def list_document_sheets(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> list[DocumentSheet]:
        """Return worksheet descriptors for ``document_id``."""

        logger.debug(
            "document.sheets.list.start",
            extra=log_context(workspace_id=workspace_id, document_id=document_id),
        )

        document = await self._get_document(workspace_id, document_id)
        storage = self._storage_for(workspace_id)
        path = storage.path_for(document.stored_uri)

        exists = await run_in_threadpool(path.exists)
        if not exists:
            raise DocumentFileMissingError(
                document_id=document_id,
                stored_uri=document.stored_uri,
            )

        suffix = Path(document.original_filename).suffix.lower()
        if suffix == ".xlsx":
            try:
                sheets = await run_in_threadpool(self._inspect_workbook, path)
                logger.info(
                    "document.sheets.list.success",
                    extra=log_context(
                        workspace_id=workspace_id,
                        document_id=document_id,
                        sheet_count=len(sheets),
                        kind="workbook",
                    ),
                )
                return sheets
            except Exception as exc:  # pragma: no cover - defensive fallback
                raise DocumentWorksheetParseError(
                    document_id=document_id,
                    stored_uri=document.stored_uri,
                    reason=type(exc).__name__,
                ) from exc

        name = self._default_sheet_name(document.original_filename)
        sheets = [DocumentSheet(name=name, index=0, kind="file", is_active=True)]
        logger.info(
            "document.sheets.list.success",
            extra=log_context(
                workspace_id=workspace_id,
                document_id=document_id,
                sheet_count=len(sheets),
                kind="fallback",
            ),
        )
        return sheets

    async def stream_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> tuple[DocumentOut, AsyncIterator[bytes]]:
        """Return a document record and async iterator for its bytes."""

        logger.debug(
            "document.stream.start",
            extra=log_context(workspace_id=workspace_id, document_id=document_id),
        )

        document = await self._get_document(workspace_id, document_id)
        storage = self._storage_for(workspace_id)
        path = storage.path_for(document.stored_uri)
        exists = await run_in_threadpool(path.exists)
        if not exists:
            logger.warning(
                "document.stream.missing_file",
                extra=log_context(
                    workspace_id=workspace_id,
                    document_id=document_id,
                    stored_uri=document.stored_uri,
                ),
            )
            raise DocumentFileMissingError(
                document_id=document_id,
                stored_uri=document.stored_uri,
            )

        stream = storage.stream(document.stored_uri)

        async def _guarded() -> AsyncIterator[bytes]:
            try:
                async for chunk in stream:
                    yield chunk
            except FileNotFoundError as exc:
                logger.warning(
                    "document.stream.file_lost_during_stream",
                    extra=log_context(
                        workspace_id=workspace_id,
                        document_id=document_id,
                        stored_uri=document.stored_uri,
                    ),
                )
                raise DocumentFileMissingError(
                    document_id=document_id,
                    stored_uri=document.stored_uri,
                ) from exc

        payload = DocumentOut.model_validate(document)
        await self._attach_last_runs(workspace_id, [payload])
        queue_context = await self.build_queue_context(workspace_id=workspace_id)
        self._apply_derived_fields(payload, queue_context)

        logger.info(
            "document.stream.ready",
            extra=log_context(
                workspace_id=workspace_id,
                document_id=document_id,
                byte_size=document.byte_size,
                content_type=document.content_type,
            ),
        )
        return payload, _guarded()

    async def delete_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        actor: User | None = None,
    ) -> None:
        """Soft delete ``document_id`` and remove the stored file."""

        actor_id: UUID | None = actor.id if actor is not None else None
        logger.debug(
            "document.delete.start",
            extra=log_context(
                workspace_id=workspace_id,
                document_id=document_id,
                user_id=actor_id,
            ),
        )

        document = await self._get_document(workspace_id, document_id)
        now = datetime.now(tz=UTC)
        document.deleted_at = now
        if actor is not None:
            document.deleted_by_user_id = actor_id
        await self._session.flush()

        storage = self._storage_for(workspace_id)
        await storage.delete(document.stored_uri)
        await self._changes.record_deleted(
            workspace_id=workspace_id,
            document_id=document_id,
        )

        logger.info(
            "document.delete.success",
            extra=log_context(
                workspace_id=workspace_id,
                document_id=document_id,
                user_id=actor_id,
                stored_uri=document.stored_uri,
            ),
        )

    async def delete_documents_batch(
        self,
        *,
        workspace_id: UUID,
        document_ids: Sequence[UUID],
        actor: User | None = None,
    ) -> list[UUID]:
        """Soft delete multiple documents and remove stored files."""

        ordered_ids = list(dict.fromkeys(document_ids))
        if not ordered_ids:
            return []

        actor_id: UUID | None = actor.id if actor is not None else None
        documents = await self._require_documents(
            workspace_id=workspace_id,
            document_ids=ordered_ids,
        )

        now = datetime.now(tz=UTC)
        for document in documents:
            document.deleted_at = now
            if actor is not None:
                document.deleted_by_user_id = actor_id

        await self._session.flush()

        storage = self._storage_for(workspace_id)
        for document in documents:
            await storage.delete(document.stored_uri)

        for document_id in ordered_ids:
            await self._changes.record_deleted(
                workspace_id=workspace_id,
                document_id=document_id,
            )

        return ordered_ids

    async def replace_document_tags(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        tags: list[str],
    ) -> DocumentOut:
        """Replace tags on a document in a single transaction."""

        try:
            normalized = normalize_tag_list(tags, max_tags=MAX_TAGS_PER_DOCUMENT)
        except TagValidationError as exc:
            raise InvalidDocumentTagsError(str(exc)) from exc

        document = await self._get_document(workspace_id, document_id)
        document.tags = [DocumentTag(document_id=document.id, tag=tag) for tag in normalized]
        await self._session.flush()

        payload = DocumentOut.model_validate(document)
        queue_context = await self.build_queue_context(workspace_id=workspace_id)
        self._apply_derived_fields(payload, queue_context)
        await self._changes.record_upsert(
            workspace_id=workspace_id,
            document_id=document_id,
            payload=payload.model_dump(),
        )
        return payload

    async def patch_document_tags(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        add: list[str] | None = None,
        remove: list[str] | None = None,
    ) -> DocumentOut:
        """Add or remove tags on a document."""

        if not add and not remove:
            raise InvalidDocumentTagsError("add or remove is required")

        try:
            normalized_add = normalize_tag_list(add or [])
            normalized_remove = normalize_tag_list(remove or [])
        except TagValidationError as exc:
            raise InvalidDocumentTagsError(str(exc)) from exc

        document = await self._get_document(workspace_id, document_id)
        existing = {tag.tag for tag in document.tags}
        next_tags = (existing | set(normalized_add)) - set(normalized_remove)
        if len(next_tags) > MAX_TAGS_PER_DOCUMENT:
            raise InvalidDocumentTagsError(f"Too many tags; max {MAX_TAGS_PER_DOCUMENT}.")

        to_remove = existing - next_tags
        if to_remove:
            document.tags = [tag for tag in document.tags if tag.tag not in to_remove]
        to_add = next_tags - existing
        for tag in to_add:
            document.tags.append(DocumentTag(document_id=document.id, tag=tag))

        await self._session.flush()

        payload = DocumentOut.model_validate(document)
        queue_context = await self.build_queue_context(workspace_id=workspace_id)
        self._apply_derived_fields(payload, queue_context)
        await self._changes.record_upsert(
            workspace_id=workspace_id,
            document_id=document_id,
            payload=payload.model_dump(),
        )
        return payload

    async def patch_document_tags_batch(
        self,
        *,
        workspace_id: UUID,
        document_ids: Sequence[UUID],
        add: list[str] | None = None,
        remove: list[str] | None = None,
    ) -> list[DocumentOut]:
        """Add or remove tags on multiple documents."""

        if not add and not remove:
            raise InvalidDocumentTagsError("add or remove is required")

        try:
            normalized_add = normalize_tag_list(add or [])
            normalized_remove = normalize_tag_list(remove or [])
        except TagValidationError as exc:
            raise InvalidDocumentTagsError(str(exc)) from exc

        ordered_ids = list(dict.fromkeys(document_ids))
        documents = await self._require_documents(
            workspace_id=workspace_id,
            document_ids=ordered_ids,
        )
        document_by_id = {doc.id: doc for doc in documents}

        for document in documents:
            existing = {tag.tag for tag in document.tags}
            next_tags = (existing | set(normalized_add)) - set(normalized_remove)
            if len(next_tags) > MAX_TAGS_PER_DOCUMENT:
                raise InvalidDocumentTagsError(f"Too many tags; max {MAX_TAGS_PER_DOCUMENT}.")

            to_remove = existing - next_tags
            if to_remove:
                document.tags = [tag for tag in document.tags if tag.tag not in to_remove]
            to_add = next_tags - existing
            for tag in to_add:
                document.tags.append(DocumentTag(document_id=document.id, tag=tag))

        await self._session.flush()

        queue_context = await self.build_queue_context(workspace_id=workspace_id)
        payloads: list[DocumentOut] = []
        for doc_id in ordered_ids:
            payload = DocumentOut.model_validate(document_by_id[doc_id])
            self._apply_derived_fields(payload, queue_context)
            payloads.append(payload)
            await self._changes.record_upsert(
                workspace_id=workspace_id,
                document_id=UUID(str(doc_id)),
                payload=payload.model_dump(),
            )

        return payloads

    async def list_tag_catalog(
        self,
        *,
        workspace_id: UUID,
        page: int,
        page_size: int,
        include_total: bool,
        q: str | None = None,
        sort: str = "name",
    ) -> TagCatalogPage:
        """Return tag catalog entries with counts."""

        try:
            normalized_q = normalize_tag_query(q)
        except TagValidationError as exc:
            raise InvalidDocumentTagsError(str(exc)) from exc

        count_expr = func.count(DocumentTag.document_id).label("document_count")
        stmt = (
            select(
                DocumentTag.tag.label("tag"),
                count_expr,
            )
            .join(Document, DocumentTag.document_id == Document.id)
            .where(
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
            .group_by(DocumentTag.tag)
        )

        if normalized_q:
            pattern = f"%{normalized_q}%"
            stmt = stmt.where(DocumentTag.tag.like(pattern))

        if sort == "-count":
            order_by = [count_expr.desc(), DocumentTag.tag.asc()]
        else:
            order_by = [DocumentTag.tag.asc()]

        offset = (page - 1) * page_size
        ordered_stmt = stmt.order_by(*order_by)

        if include_total:
            count_stmt = select(func.count()).select_from(ordered_stmt.order_by(None).subquery())
            total = (await self._session.execute(count_stmt)).scalar_one()
            result = await self._session.execute(ordered_stmt.limit(page_size).offset(offset))
            rows = result.mappings().all()
            has_next = (page * page_size) < total
        else:
            result = await self._session.execute(
                ordered_stmt.limit(page_size + 1).offset(offset)
            )
            rows = result.mappings().all()
            has_next = len(rows) > page_size
            rows = rows[:page_size]
            total = None

        items = [
            TagCatalogItem(tag=row["tag"], document_count=int(row["document_count"] or 0))
            for row in rows
        ]

        return TagCatalogPage(
            items=items,
            page=page,
            page_size=page_size,
            has_next=has_next,
            has_previous=page > 1,
            total=total,
        )

    async def _get_document(self, workspace_id: UUID, document_id: UUID) -> Document:
        document = await self._repository.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        if document is None:
            logger.warning(
                "document.get.not_found",
                extra=log_context(
                    workspace_id=workspace_id,
                    document_id=document_id,
                ),
            )
            raise DocumentNotFoundError(document_id)
        return document

    async def _require_documents(
        self,
        *,
        workspace_id: UUID,
        document_ids: Sequence[UUID],
    ) -> list[Document]:
        if not document_ids:
            return []

        stmt = (
            self._repository.base_query(workspace_id)
            .where(Document.deleted_at.is_(None))
            .where(Document.id.in_(document_ids))
        )
        result = await self._session.execute(stmt)
        documents = list(result.scalars())
        found = {doc.id for doc in documents}
        missing = [document_id for document_id in document_ids if document_id not in found]
        if missing:
            logger.warning(
                "document.require_documents.not_found",
                extra=log_context(
                    workspace_id=workspace_id,
                    document_id=str(missing[0]),
                    missing_count=len(missing),
                ),
            )
            raise DocumentNotFoundError(missing[0])

        return documents

    async def _attach_last_runs(
        self,
        workspace_id: UUID,
        documents: Sequence[DocumentOut],
    ) -> None:
        """Populate ``last_run`` on each document using recent run data."""

        if not documents:
            return

        last_runs = await self._latest_stream_runs(
            workspace_id=workspace_id,
            documents=documents,
        )
        last_successful_runs = await self._latest_successful_runs(
            workspace_id=workspace_id,
            documents=documents,
        )
        for document in documents:
            document.last_run = last_runs.get(document.id)
            document.last_successful_run = last_successful_runs.get(document.id)
            if document.last_run and document.last_run.run_at:
                document.last_run_at = document.last_run.run_at

    async def build_queue_context(self, *, workspace_id: UUID) -> DocumentQueueContext:
        has_active_configuration = await self._configs.get_active(workspace_id) is not None
        processing_paused = await self._processing_paused(workspace_id)
        queue_has_capacity = await self._queue_has_capacity()
        return DocumentQueueContext(
            has_active_configuration=has_active_configuration,
            queue_has_capacity=queue_has_capacity,
            processing_paused=processing_paused,
        )

    async def _processing_paused(self, workspace_id: UUID) -> bool:
        workspace = await self._workspaces.get_workspace(workspace_id)
        if workspace is None:
            return False
        return read_processing_paused(workspace.settings)

    async def _queue_has_capacity(self) -> bool:
        limit = self._settings.queue_size
        if not limit:
            return True
        queued = await self._runs.count_queued()
        return queued < limit

    def _apply_derived_fields(
        self,
        document: DocumentOut,
        queue_context: DocumentQueueContext | None = None,
    ) -> None:
        document.display_status = self._derive_display_status(document)
        updated_at = document.updated_at
        last_run_at = document.last_run_at
        if last_run_at is not None and last_run_at > updated_at:
            document.activity_at = last_run_at
        else:
            document.activity_at = updated_at
        if queue_context is not None:
            self._apply_queue_state(document, queue_context)

    def _apply_queue_state(self, document: DocumentOut, context: DocumentQueueContext) -> None:
        document.queue_state = None
        document.queue_reason = None

        if document.status == DocumentStatus.ARCHIVED:
            return

        last_run_status = document.last_run.status if document.last_run else None
        if last_run_status == RunStatus.QUEUED:
            document.queue_state = DocumentQueueState.QUEUED
            return
        if last_run_status == RunStatus.RUNNING:
            return
        if document.status != DocumentStatus.UPLOADED:
            return

        document.queue_state = DocumentQueueState.WAITING
        if context.processing_paused:
            document.queue_reason = DocumentQueueReason.PROCESSING_PAUSED
        elif not context.has_active_configuration:
            document.queue_reason = DocumentQueueReason.NO_ACTIVE_CONFIGURATION
        elif not context.queue_has_capacity:
            document.queue_reason = DocumentQueueReason.QUEUE_FULL

    @staticmethod
    def _derive_display_status(document: DocumentOut) -> DocumentDisplayStatus:
        if document.status == DocumentStatus.ARCHIVED:
            return DocumentDisplayStatus.ARCHIVED
        if document.status == DocumentStatus.FAILED:
            return DocumentDisplayStatus.FAILED
        if document.status == DocumentStatus.PROCESSED:
            return DocumentDisplayStatus.READY
        if document.status == DocumentStatus.PROCESSING:
            return DocumentDisplayStatus.PROCESSING
        return DocumentDisplayStatus.QUEUED

    @staticmethod
    def _status_from_last_run(status: RunStatus | None) -> DocumentStatus:
        if status == RunStatus.SUCCEEDED:
            return DocumentStatus.PROCESSED
        if status in (RunStatus.FAILED, RunStatus.CANCELLED):
            return DocumentStatus.FAILED
        if status == RunStatus.RUNNING:
            return DocumentStatus.PROCESSING
        return DocumentStatus.UPLOADED

    async def _latest_run_statuses(
        self,
        *,
        workspace_id: UUID,
        document_ids: Sequence[UUID],
    ) -> dict[UUID, RunStatus]:
        if not document_ids:
            return {}

        timestamp = func.coalesce(Run.completed_at, Run.started_at, Run.created_at)
        ranked_runs = (
            select(
                Run.input_document_id.label("document_id"),
                Run.status.label("status"),
                func.row_number()
                .over(
                    partition_by=Run.input_document_id,
                    order_by=timestamp.desc(),
                )
                .label("rank"),
            )
            .where(
                Run.workspace_id == workspace_id,
                Run.input_document_id.is_not(None),
                Run.input_document_id.in_(document_ids),
            )
            .subquery()
        )

        stmt = select(ranked_runs.c.document_id, ranked_runs.c.status).where(ranked_runs.c.rank == 1)
        result = await self._session.execute(stmt)

        latest: dict[UUID, RunStatus] = {}
        for row in result.mappings():
            document_id = row["document_id"]
            if not isinstance(document_id, UUID):
                document_id = UUID(str(document_id))
            status = row["status"]
            if not isinstance(status, RunStatus):
                status = RunStatus(str(status))
            latest[document_id] = status

        return latest

    async def _latest_stream_runs(
        self,
        *,
        workspace_id: UUID,
        documents: Sequence[DocumentOut],
    ) -> dict[UUID, DocumentLastRun]:
        doc_ids = [doc.id for doc in documents]
        if not doc_ids:
            return {}

        timestamp = func.coalesce(Run.completed_at, Run.started_at, Run.created_at)
        ranked_runs = (
            select(
                Run.input_document_id.label("document_id"),
                Run.id.label("run_id"),
                Run.status.label("status"),
                Run.error_message.label("error_message"),
                Run.completed_at.label("completed_at"),
                Run.started_at.label("started_at"),
                Run.created_at.label("created_at"),
                func.row_number()
                .over(
                    partition_by=Run.input_document_id,
                    order_by=timestamp.desc(),
                )
                .label("rank"),
            )
            .where(
                Run.workspace_id == workspace_id,
                Run.input_document_id.is_not(None),
                Run.input_document_id.in_(doc_ids),
            )
            .subquery()
        )

        stmt = select(ranked_runs).where(ranked_runs.c.rank == 1)
        result = await self._session.execute(stmt)

        latest: dict[UUID, DocumentLastRun] = {}
        for row in result.mappings():
            document_id = row["document_id"]
            if not isinstance(document_id, UUID):
                document_id = UUID(str(document_id))
            run_at = self._ensure_utc(
                row.get("completed_at") or row.get("started_at") or row.get("created_at")
            )
            message = self._last_run_message(error_message=row.get("error_message"))
            latest[document_id] = DocumentLastRun(
                run_id=row["run_id"],
                status=row["status"],
                run_at=run_at,
                message=message,
            )

        return latest

    async def _latest_successful_runs(
        self,
        *,
        workspace_id: UUID,
        documents: Sequence[DocumentOut],
    ) -> dict[UUID, DocumentLastRun]:
        doc_ids = [doc.id for doc in documents]
        if not doc_ids:
            return {}

        timestamp = func.coalesce(Run.completed_at, Run.started_at, Run.created_at)
        ranked_runs = (
            select(
                Run.input_document_id.label("document_id"),
                Run.id.label("run_id"),
                Run.status.label("status"),
                Run.error_message.label("error_message"),
                Run.completed_at.label("completed_at"),
                Run.started_at.label("started_at"),
                Run.created_at.label("created_at"),
                func.row_number()
                .over(
                    partition_by=Run.input_document_id,
                    order_by=timestamp.desc(),
                )
                .label("rank"),
            )
            .where(
                Run.workspace_id == workspace_id,
                Run.input_document_id.is_not(None),
                Run.input_document_id.in_(doc_ids),
                Run.status == RunStatus.SUCCEEDED,
            )
            .subquery()
        )

        stmt = select(ranked_runs).where(ranked_runs.c.rank == 1)
        result = await self._session.execute(stmt)

        latest: dict[UUID, DocumentLastRun] = {}
        for row in result.mappings():
            document_id = row["document_id"]
            if not isinstance(document_id, UUID):
                document_id = UUID(str(document_id))
            run_at = self._ensure_utc(
                row.get("completed_at") or row.get("started_at") or row.get("created_at")
            )
            message = self._last_run_message(error_message=row.get("error_message"))
            latest[document_id] = DocumentLastRun(
                run_id=row["run_id"],
                status=row["status"],
                run_at=run_at,
                message=message,
            )

        return latest

    @staticmethod
    def _last_run_message(*, error_message: str | None) -> str | None:
        if error_message:
            return error_message
        return None

    @staticmethod
    def _ensure_utc(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt

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
        filtered = "".join(ch for ch in candidate if unicodedata.category(ch)[0] != "C").strip()

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

    def _storage_for(self, workspace_id: UUID) -> DocumentStorage:
        base = workspace_documents_root(self._settings, workspace_id)
        return DocumentStorage(base)

    def _upload_session_storage(self, workspace_id: UUID) -> DocumentStorage:
        base = workspace_documents_root(self._settings, workspace_id)
        return DocumentStorage(base, upload_prefix=_UPLOAD_SESSION_PREFIX)

    @staticmethod
    def _parse_content_range(content_range: str) -> tuple[int, int, int]:
        match = _CONTENT_RANGE_PATTERN.match(content_range.strip())
        if not match:
            raise ValueError("Content-Range must be formatted as 'bytes start-end/total'")
        start = int(match.group(1))
        end = int(match.group(2))
        total = int(match.group(3))
        if start < 0 or end < start or total <= 0 or end >= total:
            raise ValueError("Content-Range values are invalid")
        return start, end, total

    def _next_expected_ranges(self, session: DocumentUploadSession) -> list[str]:
        if session.received_bytes >= session.byte_size:
            return []
        return [f"{session.received_bytes}-"]

    async def _require_upload_session(
        self,
        *,
        workspace_id: UUID,
        upload_session_id: UUID,
    ) -> DocumentUploadSession:
        session = await self._session.get(DocumentUploadSession, upload_session_id)
        if session is None or session.workspace_id != workspace_id:
            raise DocumentUploadSessionNotFoundError(upload_session_id)
        if session.expires_at <= utc_now():
            raise DocumentUploadSessionExpiredError(upload_session_id)
        if session.status in {DocumentUploadSessionStatus.CANCELLED, DocumentUploadSessionStatus.COMMITTED}:
            raise DocumentUploadSessionNotFoundError(upload_session_id)
        return session

    async def _write_upload_range(
        self,
        *,
        session: DocumentUploadSession,
        start: int,
        expected_size: int,
        body: AsyncIterator[bytes],
    ) -> None:
        storage = self._upload_session_storage(session.workspace_id)
        path = storage.path_for(session.temp_stored_uri)

        def _open() -> Any:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                return path.open("r+b")
            return path.open("wb")

        file_handle = await run_in_threadpool(_open)
        try:
            def _truncate_to_start() -> None:
                file_handle.seek(0, os.SEEK_END)
                current_size = file_handle.tell()
                if current_size > start:
                    file_handle.truncate(start)
                file_handle.seek(start)

            await run_in_threadpool(_truncate_to_start)

            written = 0
            async for chunk in body:
                if not chunk:
                    continue

                chunk_size = len(chunk)
                next_written = written + chunk_size
                if next_written > expected_size:
                    await run_in_threadpool(_truncate_to_start)
                    raise DocumentUploadRangeError(
                        "Uploaded bytes exceed Content-Range size",
                        next_expected_ranges=self._next_expected_ranges(session),
                    )

                await run_in_threadpool(file_handle.write, chunk)
                written = next_written

            await run_in_threadpool(file_handle.flush)
            if written != expected_size:
                await run_in_threadpool(_truncate_to_start)
                raise DocumentUploadRangeError(
                    "Uploaded bytes do not match Content-Range size",
                    next_expected_ranges=self._next_expected_ranges(session),
                )
        finally:
            await run_in_threadpool(file_handle.close)

    async def _compute_sha256(self, path: Path) -> tuple[str, int]:
        def _read() -> tuple[str, int]:
            digest = sha256()
            size = 0
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    digest.update(chunk)
            return digest.hexdigest(), size

        return await run_in_threadpool(_read)

    def _serialize_change(
        self,
        change: DocumentChange,
        queue_context: DocumentQueueContext,
    ) -> DocumentChangeEntry:
        cursor = str(change.cursor)
        if change.type == DocumentChangeType.UPSERT:
            document = DocumentOut.model_validate(change.payload)
            self._apply_derived_fields(document, queue_context)
            return DocumentChangeEntry(
                cursor=cursor,
                type="document.upsert",
                document=document,
                occurred_at=change.occurred_at,
            )
        return DocumentChangeEntry(
            cursor=cursor,
            type="document.deleted",
            document_id=str(change.document_id) if change.document_id else None,
            occurred_at=change.occurred_at,
        )

    @staticmethod
    def _inspect_workbook(path: Path) -> list[DocumentSheet]:
        with path.open("rb") as raw:
            workbook = openpyxl.load_workbook(raw, read_only=True, data_only=True)
            try:
                sheetnames = workbook.sheetnames
                active = workbook.active.title if sheetnames else None
                return [
                    DocumentSheet(
                        name=title,
                        index=index,
                        kind="worksheet",
                        is_active=title == active,
                    )
                    for index, title in enumerate(sheetnames)
                ]
            finally:
                workbook.close()

    @staticmethod
    def _default_sheet_name(name: str | None) -> str:
        stem = Path(name or "Sheet").stem.strip() or "Sheet"
        return stem[:64]


__all__ = ["DocumentsService"]
