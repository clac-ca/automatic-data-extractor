"""Service layer for document upload and retrieval."""

from __future__ import annotations

import logging
import unicodedata
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import openpyxl
from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.ids import generate_uuid7
from ade_api.common.logging import log_context
from ade_api.common.pagination import paginate_sql
from ade_api.common.types import OrderBy
from ade_api.infra.storage import workspace_documents_root
from ade_api.models import (
    Document,
    DocumentSource,
    DocumentStatus,
    DocumentTag,
    Run,
    RunStatus,
    User,
)
from ade_api.settings import Settings

from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentWorksheetParseError,
    InvalidDocumentExpirationError,
    InvalidDocumentTagsError,
)
from .filters import DocumentFilters, apply_document_filters
from .repository import DocumentsRepository
from .schemas import (
    DocumentLastRun,
    DocumentOut,
    DocumentPage,
    DocumentSheet,
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

        return DocumentOut.model_validate(hydrated)

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

    async def get_document(self, *, workspace_id: UUID, document_id: UUID) -> DocumentOut:
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

        return DocumentOut.model_validate(document)

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

        return DocumentOut.model_validate(document)

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

        return [DocumentOut.model_validate(document_by_id[doc_id]) for doc_id in ordered_ids]

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
