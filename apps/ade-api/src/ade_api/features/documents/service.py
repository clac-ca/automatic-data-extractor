"""Service layer for document upload and retrieval."""

from __future__ import annotations

import json
import logging
import unicodedata
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import openpyxl
from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.ids import generate_uuid7
from ade_api.common.logging import log_context
from ade_api.common.pagination import paginate_sql
from ade_api.common.sql import nulls_last
from ade_api.common.types import OrderBy
from ade_api.core.models import Document, DocumentSource, DocumentStatus, Run, RunStatus, User
from ade_api.infra.storage import workspace_documents_root
from ade_api.settings import Settings

from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentWorksheetParseError,
    InvalidDocumentExpirationError,
)
from .filters import DocumentFilters, apply_document_filters
from .repository import DocumentsRepository
from .schemas import DocumentLastRun, DocumentOut, DocumentPage, DocumentSheet
from .storage import DocumentStorage

logger = logging.getLogger(__name__)

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

        self._repository = DocumentsRepository(session)

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

        actor_id = cast(str | None, getattr(actor, "id", None))
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
        await self._capture_worksheet_metadata(document, storage.path_for(stored_uri))
        self._session.add(document)
        await self._session.flush()

        stmt = self._repository.base_query(workspace_id).where(Document.id == document_id)
        result = await self._session.execute(stmt)
        hydrated = result.scalar_one()

        logger.info(
            "document.create.success",
            extra=log_context(
                workspace_id=workspace_id,
                document_id=str(document_id),
                user_id=actor_id,
                content_type=document.content_type,
                byte_size=document.byte_size,
                expires_at=document.expires_at.isoformat() if document.expires_at else None,
            ),
        )

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

        actor_id = cast(str | None, getattr(actor, "id", None))
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
        )

    async def get_document(self, *, workspace_id: str, document_id: str) -> DocumentOut:
        """Return document metadata for ``document_id``."""

        logger.debug(
            "document.get.start",
            extra=log_context(workspace_id=workspace_id, document_id=document_id),
        )
        document = await self._get_document(workspace_id, document_id)
        payload = DocumentOut.model_validate(document)
        await self._attach_last_runs(workspace_id, [payload])

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

    async def list_document_sheets(
        self,
        *,
        workspace_id: str,
        document_id: str,
    ) -> list[DocumentSheet]:
        """Return worksheet descriptors for ``document_id``."""

        logger.debug(
            "document.sheets.list.start",
            extra=log_context(workspace_id=workspace_id, document_id=document_id),
        )

        document = await self._get_document(workspace_id, document_id)
        cached_sheets = self._cached_worksheets(document)
        storage = self._storage_for(workspace_id)
        path = storage.path_for(document.stored_uri)

        exists = await run_in_threadpool(path.exists)
        if not exists:
            if cached_sheets:
                logger.warning(
                    "document.sheets.cached_missing_file",
                    extra=log_context(
                        workspace_id=workspace_id,
                        document_id=document_id,
                        stored_uri=document.stored_uri,
                        cache_source="worksheets",
                    ),
                )
                return cached_sheets

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
                if cached_sheets:
                    logger.warning(
                        "document.sheets.cached_after_inspection_error",
                        extra=log_context(
                            workspace_id=workspace_id,
                            document_id=document_id,
                            stored_uri=document.stored_uri,
                            reason=type(exc).__name__,
                        ),
                    )
                    return cached_sheets

                raise DocumentWorksheetParseError(
                    document_id=document_id,
                    stored_uri=document.stored_uri,
                    reason=type(exc).__name__,
                ) from exc

        if cached_sheets:
            logger.info(
                "document.sheets.list.success",
                extra=log_context(
                    workspace_id=workspace_id,
                    document_id=document_id,
                    sheet_count=len(cached_sheets),
                    kind="cached",
                ),
            )
            return cached_sheets

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
        workspace_id: str,
        document_id: str,
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
        workspace_id: str,
        document_id: str,
        actor: User | None = None,
    ) -> None:
        """Soft delete ``document_id`` and remove the stored file."""

        actor_id = cast(str | None, getattr(actor, "id", None))
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

        logger.info(
            "document.delete.success",
            extra=log_context(
                workspace_id=workspace_id,
                document_id=document_id,
                user_id=actor_id,
                stored_uri=document.stored_uri,
            ),
        )

    async def _get_document(self, workspace_id: str, document_id: str) -> Document:
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

    async def _attach_last_runs(
        self,
        workspace_id: str,
        documents: Sequence[DocumentOut],
    ) -> None:
        """Populate ``last_run`` on each document using recent run data."""

        if not documents:
            return

        logger.debug(
            "document.last_run.attach.start",
            extra=log_context(
                workspace_id=workspace_id,
                document_count=len(documents),
            ),
        )

        run_summaries = await self._latest_stream_runs(
            workspace_id=workspace_id,
            documents=documents,
        )
        for document in documents:
            summary = run_summaries.get(document.id)
            if summary is None:
                document.last_run = None
                continue
            document.last_run = summary

        logger.debug(
            "document.last_run.attach.success",
            extra=log_context(
                workspace_id=workspace_id,
                matched_documents=len(run_summaries),
            ),
        )

    async def _latest_stream_runs(
        self,
        *,
        workspace_id: str,
        documents: Sequence[DocumentOut],
    ) -> dict[str, DocumentLastRun]:
        ids = [document.id for document in documents if document.id]
        if not ids:
            return {}

        logger.debug(
            "document.last_run.query.start",
            extra=log_context(
                workspace_id=workspace_id,
                document_count=len(ids),
            ),
        )

        ranked_runs = (
            select(
                Run.id,
                Run.input_document_id,
                Run.status,
                Run.finished_at,
                Run.started_at,
                Run.created_at,
                Run.summary,
                Run.error_message,
                func.row_number()
                .over(
                    partition_by=Run.input_document_id,
                    order_by=(
                        *nulls_last(Run.finished_at.desc()),
                        *nulls_last(Run.started_at.desc()),
                        *nulls_last(Run.created_at.desc()),
                    ),
                )
                .label("run_rank"),
            )
            .where(
                Run.workspace_id == workspace_id,
                Run.input_document_id.in_(ids),
            )
        ).subquery()

        stmt = (
            select(
                ranked_runs.c.id,
                ranked_runs.c.input_document_id,
                ranked_runs.c.status,
                ranked_runs.c.finished_at,
                ranked_runs.c.started_at,
                ranked_runs.c.created_at,
                ranked_runs.c.summary,
                ranked_runs.c.error_message,
            )
            .where(ranked_runs.c.run_rank == 1)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        latest: dict[str, DocumentLastRun] = {}
        for row in rows:
            doc_id = row.input_document_id
            if doc_id is None:
                continue
            timestamp = row.finished_at or row.started_at or row.created_at
            status_value = (
                RunStatus.CANCELED if row.status == RunStatus.CANCELED else row.status
            )
            summary_payload = None
            if row.summary:
                try:
                    parsed = json.loads(row.summary)
                    summary_payload = parsed if isinstance(parsed, dict) else None
                except json.JSONDecodeError:
                    summary_payload = None
            message = row.error_message
            if summary_payload:
                run_block = summary_payload.get("run", {})
                message = (
                    run_block.get("failure_message")
                    or message
                    or run_block.get("status")
                )
            latest[doc_id] = DocumentLastRun(
                run_id=row.id,
                status=status_value,
                run_at=(
                    timestamp
                    if timestamp is None or timestamp.tzinfo
                    else timestamp.replace(tzinfo=UTC)
                ),
                message=message,
            )

        logger.debug(
            "document.last_run.query.success",
            extra=log_context(
                workspace_id=workspace_id,
                document_count=len(ids),
                matched_runs=len(latest),
            ),
        )
        return latest

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

    def _cached_worksheets(self, document: Document) -> list[DocumentSheet] | None:
        """Return cached worksheet metadata stored on the document, if any."""

        attrs = document.attributes if isinstance(document.attributes, Mapping) else {}
        cached = attrs.get("worksheets") if isinstance(attrs, Mapping) else None
        if not isinstance(cached, Sequence) or isinstance(cached, (str, bytes, bytearray)):
            return None

        valid: list[DocumentSheet] = []
        for entry in cached:
            try:
                valid.append(DocumentSheet.model_validate(entry))
            except Exception:  # pragma: no cover - defensive
                continue

        return valid or None

    async def _capture_worksheet_metadata(self, document: Document, path: Path) -> None:
        """Persist worksheet descriptors on the document for later reuse."""

        suffix = Path(document.original_filename).suffix.lower()
        try:
            if suffix == ".xlsx":
                sheets = await run_in_threadpool(self._inspect_workbook, path)
            else:
                sheet_name = self._default_sheet_name(document.original_filename)
                sheets = [DocumentSheet(name=sheet_name, index=0, kind="file", is_active=True)]
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning(
                "document.sheets.cache_failed",
                extra=log_context(
                    workspace_id=document.workspace_id,
                    document_id=document.id,
                    stored_uri=document.stored_uri,
                    reason=type(exc).__name__,
                ),
            )
            return

        document.attributes["worksheets"] = [sheet.model_dump() for sheet in sheets]

    def _storage_for(self, workspace_id: str) -> DocumentStorage:
        base = workspace_documents_root(self._settings, workspace_id)
        return DocumentStorage(base)

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
