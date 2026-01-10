"""Service layer for document upload and retrieval."""

from __future__ import annotations

import logging
import math
import unicodedata
from collections.abc import Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import openpyxl
from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ade_api.common.etag import build_etag_token, format_weak_etag
from ade_api.common.ids import generate_uuid7
from ade_api.common.list_filters import FilterItem, FilterJoinOperator
from ade_api.common.listing import paginate_query
from ade_api.common.logging import log_context
from ade_api.common.sorting import resolve_sort
from ade_api.common.types import OrderBy
from ade_api.common.workbook_preview import (
    WorkbookSheetPreview,
    build_workbook_preview_from_csv,
    build_workbook_preview_from_xlsx,
)
from ade_api.infra.storage import workspace_documents_root
from ade_api.models import (
    Document,
    DocumentEvent,
    DocumentEventType,
    DocumentSource,
    DocumentStatus,
    DocumentTag,
    Run,
    RunStatus,
    User,
)
from ade_api.settings import Settings

from .change_feed import DocumentEventsService
from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentPreviewParseError,
    DocumentPreviewSheetNotFoundError,
    DocumentPreviewUnsupportedError,
    DocumentWorksheetParseError,
    InvalidDocumentExpirationError,
    InvalidDocumentTagsError,
)
from .filters import apply_document_filters
from .repository import DocumentsRepository
from .schemas import (
    DocumentChangeEntry,
    DocumentChangesPage,
    DocumentFileType,
    DocumentListPage,
    DocumentListRow,
    DocumentOut,
    DocumentResultSummary,
    DocumentRunSummary,
    DocumentSheet,
    DocumentUpdateRequest,
    DocumentUploadRunOptions,
    TagCatalogItem,
    TagCatalogPage,
)
from .storage import DocumentStorage, StoredDocument
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

def _run_with_timeout(func, *, timeout: float, **kwargs):
    """Run a callable with a timeout to avoid hanging on large workbook operations."""
    if timeout <= 0:
        return func(**kwargs)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, **kwargs)
        return future.result(timeout=timeout)



@dataclass(slots=True)
class StagedUpload:
    document_id: UUID
    stored_uri: str
    stored: StoredDocument


class DocumentsService:
    """Manage document metadata and backing file storage."""

    def __init__(self, *, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

        documents_dir = settings.documents_dir
        if documents_dir is None:
            raise RuntimeError("Document storage directory is not configured")

        self._repository = DocumentsRepository(session)
        self._events = DocumentEventsService(session=session, settings=settings)

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

    def create_document(
        self,
        *,
        workspace_id: UUID,
        upload: UploadFile,
        metadata: Mapping[str, Any] | None = None,
        expires_at: str | None = None,
        actor: User | None = None,
        staged: StagedUpload | None = None,
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

        owns_stage = staged is None
        staged_upload = staged or self.stage_upload(workspace_id=workspace_id, upload=upload)
        document_id = staged_upload.document_id
        stored_uri = staged_upload.stored_uri
        stored = staged_upload.stored

        try:
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
            self._session.flush()
        except Exception:
            if owns_stage:
                self.discard_staged_upload(workspace_id=workspace_id, staged=staged_upload)
            raise

        stmt = self._repository.base_query(workspace_id).where(Document.id == document_id)
        result = self._session.execute(stmt)
        hydrated = result.scalar_one()

        payload = DocumentOut.model_validate(hydrated)
        self._apply_derived_fields(payload)
        payload.list_row = self._build_list_row(payload)
        self._events.record_changed(
            workspace_id=workspace_id,
            document_id=document_id,
            document_version=payload.version,
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

    def stage_upload(
        self,
        *,
        workspace_id: UUID,
        upload: UploadFile,
        document_id: UUID | None = None,
    ) -> StagedUpload:
        document_id = document_id or generate_uuid7()
        storage = self._storage_for(workspace_id)
        stored_uri = storage.make_stored_uri(str(document_id))
        if upload.file is None:  # pragma: no cover - UploadFile always supplies file
            raise RuntimeError("Upload stream is not available")
        stored = storage.write(
            stored_uri,
            upload.file,
            max_bytes=self._settings.storage_upload_max_bytes,
        )
        return StagedUpload(document_id=document_id, stored_uri=stored_uri, stored=stored)

    def discard_staged_upload(self, *, workspace_id: UUID, staged: StagedUpload) -> None:
        storage = self._storage_for(workspace_id)
        storage.delete(staged.stored_uri)

    def list_documents(
        self,
        *,
        workspace_id: UUID,
        page: int,
        per_page: int,
        order_by: OrderBy,
        filters: list[FilterItem],
        join_operator: FilterJoinOperator,
        q: str | None,
    ) -> DocumentListPage:
        """Return paginated documents with the shared envelope."""

        logger.debug(
            "document.list.start",
            extra=log_context(
                workspace_id=workspace_id,
                page=page,
                per_page=per_page,
                order_by=str(order_by),
            ),
        )

        stmt = self._repository.base_query(workspace_id).where(Document.deleted_at.is_(None))
        stmt = apply_document_filters(
            stmt,
            filters,
            join_operator=join_operator,
            q=q,
        )

        # Capture the cursor before listing to avoid skipping changes committed during the query.
        changes_cursor = self._events.current_cursor(workspace_id=workspace_id)
        page_result = paginate_query(
            self._session,
            stmt,
            page=page,
            per_page=per_page,
            order_by=order_by,
            changes_cursor=str(changes_cursor),
        )
        items = [DocumentOut.model_validate(item) for item in page_result.items]
        self._attach_latest_runs(workspace_id, items)
        for item in items:
            self._apply_derived_fields(item)

        logger.info(
            "document.list.success",
            extra=log_context(
                workspace_id=workspace_id,
                page=page_result.page,
                per_page=page_result.per_page,
                count=len(items),
                total=page_result.total,
            ),
        )

        rows = [self._build_list_row(item) for item in items]

        return DocumentListPage(
            items=rows,
            page=page_result.page,
            per_page=page_result.per_page,
            page_count=page_result.page_count,
            total=page_result.total,
            changes_cursor=page_result.changes_cursor,
        )

    def list_document_changes(
        self,
        *,
        workspace_id: UUID,
        cursor_token: str,
        limit: int,
        max_cursor: int | None = None,
        include_rows: bool = False,
    ) -> DocumentChangesPage:
        try:
            cursor = int(cursor_token)
        except (TypeError, ValueError) as exc:
            raise ValueError("cursor must be an integer string") from exc

        page = self._events.list_changes(
            workspace_id=workspace_id,
            cursor=cursor,
            limit=limit,
            max_cursor=max_cursor,
        )
        entries = self.build_change_entries(
            workspace_id=workspace_id,
            events=page.items,
            include_rows=include_rows,
        )
        return DocumentChangesPage(items=entries, next_cursor=str(page.next_cursor))

    def build_change_entries(
        self,
        *,
        workspace_id: UUID,
        events: Sequence[DocumentEvent],
        include_rows: bool,
    ) -> list[DocumentChangeEntry]:
        rows_by_id: dict[UUID, DocumentListRow] = {}
        if include_rows:
            changed_ids = {
                change.document_id
                for change in events
                if change.event_type == DocumentEventType.CHANGED
            }
            if changed_ids:
                stmt = (
                    self._repository.base_query(workspace_id)
                    .where(Document.id.in_(changed_ids))
                    .where(Document.deleted_at.is_(None))
                )
                result = self._session.execute(stmt)
                documents = list(result.scalars())
                payloads = [DocumentOut.model_validate(item) for item in documents]
                self._attach_latest_runs(workspace_id, payloads)
                for payload in payloads:
                    self._apply_derived_fields(payload)
                    rows_by_id[payload.id] = self._build_list_row(payload)

        entries: list[DocumentChangeEntry] = []
        for change in events:
            row = None
            if include_rows and change.event_type == DocumentEventType.CHANGED:
                row = rows_by_id.get(change.document_id)
            entries.append(
                DocumentChangeEntry(
                    cursor=str(change.cursor),
                    type=change.event_type.value,
                    document_id=str(change.document_id),
                    occurred_at=change.occurred_at,
                    document_version=change.document_version,
                    request_id=change.request_id,
                    client_request_id=change.client_request_id,
                    row=row,
                )
            )
        return entries

    def get_document(self, *, workspace_id: UUID, document_id: UUID) -> DocumentOut:
        """Return document metadata for ``document_id``."""

        logger.debug(
            "document.get.start",
            extra=log_context(workspace_id=workspace_id, document_id=document_id),
        )
        document = self._get_document(workspace_id, document_id)
        payload = DocumentOut.model_validate(document)
        self._attach_latest_runs(workspace_id, [payload])
        self._apply_derived_fields(payload)

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

    def get_document_list_row(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> DocumentListRow:
        """Return a table-ready row projection for ``document_id``."""

        logger.debug(
            "document.list_row.start",
            extra=log_context(workspace_id=workspace_id, document_id=document_id),
        )
        document = self._get_document(workspace_id, document_id)
        payload = DocumentOut.model_validate(document)
        self._attach_latest_runs(workspace_id, [payload])
        self._apply_derived_fields(payload)
        row = self._build_list_row(payload)

        logger.info(
            "document.list_row.success",
            extra=log_context(
                workspace_id=workspace_id,
                document_id=document_id,
                status=document.status,
                byte_size=document.byte_size,
            ),
        )
        return row

    def update_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        payload: DocumentUpdateRequest,
        client_request_id: str | None = None,
    ) -> DocumentOut:
        document = self._get_document(workspace_id, document_id)
        changed = False

        if "assignee_user_id" in payload.model_fields_set:
            if document.assignee_user_id != payload.assignee_user_id:
                document.assignee_user_id = payload.assignee_user_id
                changed = True
        if "metadata" in payload.model_fields_set and payload.metadata is not None:
            next_metadata = dict(payload.metadata)
            if document.attributes != next_metadata:
                document.attributes = next_metadata
                changed = True

        if changed:
            document.version += 1

        if changed:
            self._session.flush()
            self._session.refresh(document, attribute_names=["assignee_user"])

        updated = DocumentOut.model_validate(document)
        self._apply_derived_fields(updated)
        if changed:
            self._events.record_changed(
                workspace_id=workspace_id,
                document_id=document_id,
                document_version=updated.version,
                client_request_id=client_request_id,
            )
        return updated

    def archive_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        client_request_id: str | None = None,
    ) -> DocumentOut:
        """Archive a document to remove it from active workflows."""

        document = self._get_document(workspace_id, document_id)
        changed = document.status != DocumentStatus.ARCHIVED
        if changed:
            document.status = DocumentStatus.ARCHIVED
            document.version += 1
            self._session.flush()

        payload = DocumentOut.model_validate(document)
        self._apply_derived_fields(payload)
        if changed:
            self._events.record_changed(
                workspace_id=workspace_id,
                document_id=document_id,
                document_version=payload.version,
                client_request_id=client_request_id,
            )
        return payload

    def archive_documents_batch(
        self,
        *,
        workspace_id: UUID,
        document_ids: Sequence[UUID],
        client_request_id: str | None = None,
    ) -> list[DocumentOut]:
        """Archive multiple documents."""

        ordered_ids = list(dict.fromkeys(document_ids))
        if not ordered_ids:
            return []

        documents = self._require_documents(
            workspace_id=workspace_id,
            document_ids=ordered_ids,
        )
        document_by_id = {doc.id: doc for doc in documents}
        document_by_id = {doc.id: doc for doc in documents}
        changed_ids: set[UUID] = set()

        for document in documents:
            if document.status == DocumentStatus.ARCHIVED:
                continue
            document.status = DocumentStatus.ARCHIVED
            document.version += 1
            changed_ids.add(document.id)

        if changed_ids:
            self._session.flush()

        payloads: list[DocumentOut] = []
        for doc_id in ordered_ids:
            payload = DocumentOut.model_validate(document_by_id[doc_id])
            self._apply_derived_fields(payload)
            payloads.append(payload)
            if doc_id in changed_ids:
                self._events.record_changed(
                    workspace_id=workspace_id,
                    document_id=doc_id,
                    document_version=payload.version,
                    client_request_id=client_request_id,
                )

        return payloads

    def restore_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        client_request_id: str | None = None,
    ) -> DocumentOut:
        """Restore a document from the archive."""

        document = self._get_document(workspace_id, document_id)
        if document.status != DocumentStatus.ARCHIVED:
            payload = DocumentOut.model_validate(document)
            self._apply_derived_fields(payload)
            return payload

        status_map = self._latest_run_statuses(
            workspace_id=workspace_id,
            document_ids=[document.id],
        )
        document.status = self._status_from_last_run(status_map.get(document.id))
        document.version += 1
        self._session.flush()

        payload = DocumentOut.model_validate(document)
        self._apply_derived_fields(payload)
        self._events.record_changed(
            workspace_id=workspace_id,
            document_id=document_id,
            document_version=payload.version,
            client_request_id=client_request_id,
        )
        return payload

    def restore_documents_batch(
        self,
        *,
        workspace_id: UUID,
        document_ids: Sequence[UUID],
        client_request_id: str | None = None,
    ) -> list[DocumentOut]:
        """Restore multiple documents from the archive."""

        ordered_ids = list(dict.fromkeys(document_ids))
        if not ordered_ids:
            return []

        documents = self._require_documents(
            workspace_id=workspace_id,
            document_ids=ordered_ids,
        )
        document_by_id = {doc.id: doc for doc in documents}
        status_map = self._latest_run_statuses(
            workspace_id=workspace_id,
            document_ids=list(document_by_id.keys()),
        )
        changed_ids: set[UUID] = set()

        for document in documents:
            if document.status != DocumentStatus.ARCHIVED:
                continue
            document.status = self._status_from_last_run(status_map.get(document.id))
            document.version += 1
            changed_ids.add(document.id)

        if changed_ids:
            self._session.flush()

        payloads: list[DocumentOut] = []
        for doc_id in ordered_ids:
            payload = DocumentOut.model_validate(document_by_id[doc_id])
            self._apply_derived_fields(payload)
            payloads.append(payload)
            if doc_id in changed_ids:
                self._events.record_changed(
                    workspace_id=workspace_id,
                    document_id=doc_id,
                    document_version=payload.version,
                    client_request_id=client_request_id,
                )

        return payloads

    def list_document_sheets(
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

        document = self._get_document(workspace_id, document_id)
        storage = self._storage_for(workspace_id)
        path = storage.path_for(document.stored_uri)

        if not path.exists():
            raise DocumentFileMissingError(
                document_id=document_id,
                stored_uri=document.stored_uri,
            )

        suffix = Path(document.original_filename).suffix.lower()
        if suffix == ".xlsx":
            try:
                sheets = _run_with_timeout(
                    self._inspect_workbook,
                    timeout=self._settings.preview_timeout_seconds,
                    path=path,
                )
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
            except FuturesTimeout as exc:
                raise DocumentWorksheetParseError(
                    document_id=document_id,
                    stored_uri=document.stored_uri,
                    reason="timeout",
                ) from exc
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

    def get_document_preview(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        max_rows: int,
        max_columns: int,
        trim_empty_columns: bool = False,
        trim_empty_rows: bool = False,
        sheet_name: str | None = None,
        sheet_index: int | None = None,
    ) -> WorkbookSheetPreview:
        """Return a table-ready preview for a document workbook."""

        effective_sheet_index = sheet_index
        if sheet_name is None and sheet_index is None:
            effective_sheet_index = 0

        logger.debug(
            "document.preview.start",
            extra=log_context(
                workspace_id=workspace_id,
                document_id=document_id,
                sheet_name=sheet_name,
                sheet_index=effective_sheet_index,
            ),
        )

        document = self._get_document(workspace_id, document_id)
        storage = self._storage_for(workspace_id)
        path = storage.path_for(document.stored_uri)

        if not path.exists():
            raise DocumentFileMissingError(
                document_id=document_id,
                stored_uri=document.stored_uri,
            )

        suffix = Path(document.original_filename).suffix.lower()
        try:
            if suffix == ".xlsx":
                preview = _run_with_timeout(
                    build_workbook_preview_from_xlsx,
                    timeout=self._settings.preview_timeout_seconds,
                    path=path,
                    max_rows=max_rows,
                    max_columns=max_columns,
                    trim_empty_columns=trim_empty_columns,
                    trim_empty_rows=trim_empty_rows,
                    sheet_name=sheet_name,
                    sheet_index=effective_sheet_index,
                )
            elif suffix == ".csv":
                preview = _run_with_timeout(
                    build_workbook_preview_from_csv,
                    timeout=self._settings.preview_timeout_seconds,
                    path=path,
                    max_rows=max_rows,
                    max_columns=max_columns,
                    trim_empty_columns=trim_empty_columns,
                    trim_empty_rows=trim_empty_rows,
                    sheet_name=sheet_name,
                    sheet_index=effective_sheet_index,
                )
            else:
                raise DocumentPreviewUnsupportedError(
                    document_id=document_id,
                    file_type=suffix or "unknown",
                )
        except (KeyError, IndexError) as exc:
            requested = sheet_name if sheet_name is not None else str(effective_sheet_index)
            raise DocumentPreviewSheetNotFoundError(
                document_id=document_id,
                sheet=requested,
            ) from exc
        except FuturesTimeout as exc:
            raise DocumentPreviewParseError(
                document_id=document_id,
                stored_uri=document.stored_uri,
                reason="timeout",
            ) from exc
        except DocumentPreviewUnsupportedError:
            raise
        except Exception as exc:  # pragma: no cover - defensive fallback
            raise DocumentPreviewParseError(
                document_id=document_id,
                stored_uri=document.stored_uri,
                reason=type(exc).__name__,
            ) from exc

        logger.info(
            "document.preview.success",
            extra=log_context(
                workspace_id=workspace_id,
                document_id=document_id,
                sheet_name=preview.name,
                sheet_index=preview.index,
            ),
        )
        return preview

    def stream_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> tuple[DocumentOut, Iterator[bytes]]:
        """Return a document record and iterator for its bytes."""

        logger.debug(
            "document.stream.start",
            extra=log_context(workspace_id=workspace_id, document_id=document_id),
        )

        document = self._get_document(workspace_id, document_id)
        storage = self._storage_for(workspace_id)
        path = storage.path_for(document.stored_uri)
        if not path.exists():
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

        def _guarded() -> Iterator[bytes]:
            try:
                for chunk in stream:
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
        self._attach_latest_runs(workspace_id, [payload])
        self._apply_derived_fields(payload)

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

    def delete_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        actor: User | None = None,
        client_request_id: str | None = None,
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

        document = self._get_document(workspace_id, document_id)
        now = datetime.now(tz=UTC)
        document.deleted_at = now
        document.version += 1
        if actor is not None:
            document.deleted_by_user_id = actor_id
        self._session.flush()

        storage = self._storage_for(workspace_id)
        storage.delete(document.stored_uri)
        self._events.record_deleted(
            workspace_id=workspace_id,
            document_id=document_id,
            document_version=document.version,
            client_request_id=client_request_id,
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

    def delete_documents_batch(
        self,
        *,
        workspace_id: UUID,
        document_ids: Sequence[UUID],
        actor: User | None = None,
        client_request_id: str | None = None,
    ) -> list[UUID]:
        """Soft delete multiple documents and remove stored files."""

        ordered_ids = list(dict.fromkeys(document_ids))
        if not ordered_ids:
            return []

        actor_id: UUID | None = actor.id if actor is not None else None
        documents = self._require_documents(
            workspace_id=workspace_id,
            document_ids=ordered_ids,
        )
        document_by_id = {doc.id: doc for doc in documents}

        now = datetime.now(tz=UTC)
        for document in documents:
            document.deleted_at = now
            document.version += 1
            if actor is not None:
                document.deleted_by_user_id = actor_id

        self._session.flush()

        storage = self._storage_for(workspace_id)
        for document in documents:
            storage.delete(document.stored_uri)

        for document_id in ordered_ids:
            document = document_by_id[document_id]
            self._events.record_deleted(
                workspace_id=workspace_id,
                document_id=document_id,
                document_version=document.version,
                client_request_id=client_request_id,
            )

        return ordered_ids

    def replace_document_tags(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        tags: list[str],
        client_request_id: str | None = None,
    ) -> DocumentOut:
        """Replace tags on a document in a single transaction."""

        try:
            normalized = normalize_tag_list(tags, max_tags=MAX_TAGS_PER_DOCUMENT)
        except TagValidationError as exc:
            raise InvalidDocumentTagsError(str(exc)) from exc

        document = self._get_document(workspace_id, document_id)
        document.tags = [DocumentTag(document_id=document.id, tag=tag) for tag in normalized]
        document.version += 1
        self._session.flush()

        payload = DocumentOut.model_validate(document)
        self._apply_derived_fields(payload)
        self._events.record_changed(
            workspace_id=workspace_id,
            document_id=document_id,
            document_version=payload.version,
            client_request_id=client_request_id,
        )
        return payload

    def patch_document_tags(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        add: list[str] | None = None,
        remove: list[str] | None = None,
        client_request_id: str | None = None,
    ) -> DocumentOut:
        """Add or remove tags on a document."""

        if not add and not remove:
            raise InvalidDocumentTagsError("add or remove is required")

        try:
            normalized_add = normalize_tag_list(add or [])
            normalized_remove = normalize_tag_list(remove or [])
        except TagValidationError as exc:
            raise InvalidDocumentTagsError(str(exc)) from exc

        document = self._get_document(workspace_id, document_id)
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

        document.version += 1
        self._session.flush()

        payload = DocumentOut.model_validate(document)
        self._apply_derived_fields(payload)
        self._events.record_changed(
            workspace_id=workspace_id,
            document_id=document_id,
            document_version=payload.version,
            client_request_id=client_request_id,
        )
        return payload

    def patch_document_tags_batch(
        self,
        *,
        workspace_id: UUID,
        document_ids: Sequence[UUID],
        add: list[str] | None = None,
        remove: list[str] | None = None,
        client_request_id: str | None = None,
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
        documents = self._require_documents(
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

            document.version += 1

        self._session.flush()

        payloads: list[DocumentOut] = []
        for doc_id in ordered_ids:
            payload = DocumentOut.model_validate(document_by_id[doc_id])
            self._apply_derived_fields(payload)
            payloads.append(payload)
            self._events.record_changed(
                workspace_id=workspace_id,
                document_id=UUID(str(doc_id)),
                document_version=payload.version,
                client_request_id=client_request_id,
            )

        return payloads

    def list_tag_catalog(
        self,
        *,
        workspace_id: UUID,
        page: int,
        per_page: int,
        sort: list[str],
        q: str | None = None,
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

        sort_fields = {
            "name": (DocumentTag.tag.asc(), DocumentTag.tag.desc()),
            "count": (count_expr.asc(), count_expr.desc()),
        }
        order_by = resolve_sort(
            sort,
            allowed=sort_fields,
            default=["name"],
            id_field=(DocumentTag.tag.asc(), DocumentTag.tag.desc()),
        )

        offset = (page - 1) * per_page
        ordered_stmt = stmt.order_by(*order_by)

        count_stmt = select(func.count()).select_from(ordered_stmt.order_by(None).subquery())
        total = (self._session.execute(count_stmt)).scalar_one()
        page_count = math.ceil(total / per_page) if total > 0 else 0
        result = self._session.execute(ordered_stmt.limit(per_page).offset(offset))
        rows = result.mappings().all()

        items = [
            TagCatalogItem(tag=row["tag"], document_count=int(row["document_count"] or 0))
            for row in rows
        ]

        return TagCatalogPage(
            items=items,
            page=page,
            per_page=per_page,
            page_count=page_count,
            total=total,
            changes_cursor="0",
        )

    def _get_document(self, workspace_id: UUID, document_id: UUID) -> Document:
        document = self._repository.get_document(
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

    def _require_documents(
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
        result = self._session.execute(stmt)
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

    def _attach_latest_runs(
        self,
        workspace_id: UUID,
        documents: Sequence[DocumentOut],
    ) -> None:
        """Populate latest run summaries on each document."""

        if not documents:
            return

        latest_runs = self._latest_stream_runs(
            workspace_id=workspace_id,
            documents=documents,
        )
        latest_successful_runs = self._latest_successful_runs(
            workspace_id=workspace_id,
            documents=documents,
        )
        for document in documents:
            document.latest_run = latest_runs.get(document.id)
            document.latest_successful_run = latest_successful_runs.get(document.id)

    def _apply_derived_fields(self, document: DocumentOut) -> None:
        updated_at = document.updated_at
        latest_at = self._latest_run_at(document.latest_run)
        document.activity_at = latest_at if latest_at and latest_at > updated_at else updated_at
        document.latest_result = self._derive_latest_result(document)
        document.etag = format_weak_etag(build_etag_token(document.id, document.version))

    def _build_list_row(self, document: DocumentOut) -> DocumentListRow:
        activity_at = document.activity_at or document.updated_at
        return DocumentListRow(
            id=document.id,
            workspace_id=document.workspace_id,
            name=document.name,
            file_type=self._derive_file_type(document.name),
            status=document.status,
            uploader=document.uploader,
            assignee=document.assignee,
            tags=document.tags,
            byte_size=document.byte_size,
            created_at=document.created_at,
            updated_at=document.updated_at,
            activity_at=activity_at,
            version=document.version,
            etag=document.etag,
            latest_run=document.latest_run,
            latest_successful_run=document.latest_successful_run,
            latest_result=document.latest_result,
        )

    @staticmethod
    def _derive_file_type(name: str) -> DocumentFileType:
        suffix = Path(name).suffix.lower().lstrip(".")
        if suffix == "xlsx":
            return DocumentFileType.XLSX
        if suffix == "xls":
            return DocumentFileType.XLS
        if suffix == "csv":
            return DocumentFileType.CSV
        if suffix == "pdf":
            return DocumentFileType.PDF
        return DocumentFileType.UNKNOWN

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        return None

    @classmethod
    def _derive_latest_result(cls, document: DocumentOut) -> DocumentResultSummary:
        metadata = document.metadata or {}
        candidate = (
            metadata.get("mapping")
            or metadata.get("mapping_health")
            or metadata.get("mapping_quality")
        )
        if isinstance(candidate, Mapping):
            attention = cls._coerce_int(candidate.get("issues"))
            if attention is None:
                attention = cls._coerce_int(candidate.get("attention")) or 0
            unmapped = cls._coerce_int(candidate.get("unmapped")) or 0
            pending = candidate.get("status") == "pending"
            return DocumentResultSummary(
                attention=attention,
                unmapped=unmapped,
                pending=True if pending else None,
            )

        attention = cls._coerce_int(metadata.get("mapping_issues"))
        unmapped = cls._coerce_int(metadata.get("unmapped_columns"))
        if attention is not None or unmapped is not None:
            return DocumentResultSummary(
                attention=attention or 0,
                unmapped=unmapped or 0,
            )

        if document.status in {DocumentStatus.UPLOADED, DocumentStatus.PROCESSING}:
            return DocumentResultSummary(attention=0, unmapped=0, pending=True)

        return DocumentResultSummary(attention=0, unmapped=0)

    @staticmethod
    def _latest_run_at(run: DocumentRunSummary | None) -> datetime | None:
        if run is None:
            return None
        return run.completed_at or run.started_at

    @staticmethod
    def _status_from_last_run(status: RunStatus | None) -> DocumentStatus:
        if status == RunStatus.SUCCEEDED:
            return DocumentStatus.PROCESSED
        if status == RunStatus.FAILED:
            return DocumentStatus.FAILED
        if status == RunStatus.RUNNING:
            return DocumentStatus.PROCESSING
        return DocumentStatus.UPLOADED

    def _latest_run_statuses(
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

        stmt = (
            select(ranked_runs.c.document_id, ranked_runs.c.status)
            .where(ranked_runs.c.rank == 1)
        )
        result = self._session.execute(stmt)

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

    def _latest_stream_runs(
        self,
        *,
        workspace_id: UUID,
        documents: Sequence[DocumentOut],
    ) -> dict[UUID, DocumentRunSummary]:
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
        result = self._session.execute(stmt)

        latest: dict[UUID, DocumentRunSummary] = {}
        for row in result.mappings():
            document_id = row["document_id"]
            if not isinstance(document_id, UUID):
                document_id = UUID(str(document_id))
            latest[document_id] = DocumentRunSummary(
                id=row["run_id"],
                status=row["status"],
                started_at=self._ensure_utc(row.get("started_at") or row.get("created_at")),
                completed_at=self._ensure_utc(row.get("completed_at")),
                error_summary=self._last_run_message(error_message=row.get("error_message")),
            )

        return latest

    def _latest_successful_runs(
        self,
        *,
        workspace_id: UUID,
        documents: Sequence[DocumentOut],
    ) -> dict[UUID, DocumentRunSummary]:
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
        result = self._session.execute(stmt)

        latest: dict[UUID, DocumentRunSummary] = {}
        for row in result.mappings():
            document_id = row["document_id"]
            if not isinstance(document_id, UUID):
                document_id = UUID(str(document_id))
            latest[document_id] = DocumentRunSummary(
                id=row["run_id"],
                status=row["status"],
                started_at=self._ensure_utc(row.get("started_at") or row.get("created_at")),
                completed_at=self._ensure_utc(row.get("completed_at")),
                error_summary=self._last_run_message(error_message=row.get("error_message")),
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

    @staticmethod
    def _inspect_workbook(path: Path) -> list[DocumentSheet]:
        with path.open("rb") as raw:
            workbook = openpyxl.load_workbook(
                raw,
                read_only=True,
                data_only=True,
                keep_links=False,
            )
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
