from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    Security,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sse_starlette.sse import EventSourceResponse

from ade_api.api.deps import (
    SettingsDep,
    get_documents_service,
    get_idempotency_service,
    get_runs_service,
)
from ade_api.common.concurrency import require_if_match
from ade_api.common.downloads import build_content_disposition
from ade_api.common.etag import build_etag_token, format_weak_etag
from ade_api.common.listing import ListQueryParams, list_query_params, strict_list_query_guard
from ade_api.common.logging import log_context
from ade_api.common.sorting import resolve_sort
from ade_api.common.sse import sse_json
from ade_api.common.workbook_preview import (
    DEFAULT_PREVIEW_COLUMNS,
    DEFAULT_PREVIEW_ROWS,
    MAX_PREVIEW_COLUMNS,
    MAX_PREVIEW_ROWS,
    WorkbookSheetPreview,
)
from ade_api.core.http import require_authenticated, require_csrf, require_workspace
from ade_api.db import get_sessionmaker
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.idempotency import (
    IdempotencyService,
    build_request_hash,
    build_scope_key,
    require_idempotency_key,
)
from ade_api.features.runs.exceptions import RunQueueFullError
from ade_api.features.runs.schemas import RunCreateOptionsBase
from ade_api.features.runs.service import RunsService
from ade_api.models import User

from .change_feed import DocumentEventCursorTooOld, DocumentEventsService
from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentPreviewParseError,
    DocumentPreviewSheetNotFoundError,
    DocumentPreviewUnsupportedError,
    DocumentTooLargeError,
    DocumentWorksheetParseError,
    InvalidDocumentExpirationError,
    InvalidDocumentTagsError,
)
from .schemas import (
    DocumentBatchArchiveRequest,
    DocumentBatchArchiveResponse,
    DocumentBatchDeleteRequest,
    DocumentBatchDeleteResponse,
    DocumentBatchTagsRequest,
    DocumentBatchTagsResponse,
    DocumentChangesPage,
    DocumentListPage,
    DocumentListRow,
    DocumentOut,
    DocumentSheet,
    DocumentTagsPatch,
    DocumentTagsReplace,
    DocumentUpdateRequest,
    DocumentUploadRunOptions,
    TagCatalogPage,
)
from .service import DocumentsService
from .sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS

router = APIRouter(
    prefix="/workspaces/{workspaceId}/documents",
    tags=["documents"],
    dependencies=[Security(require_authenticated)],
)
tags_router = APIRouter(
    prefix="/workspaces/{workspaceId}/documents",
    tags=["documents"],
    dependencies=[Security(require_authenticated)],
)

logger = logging.getLogger(__name__)

TAILER_POLL_INTERVAL_SECONDS = 0.25
TAILER_POLL_MAX_INTERVAL_SECONDS = 2.0
TAILER_BATCH_LIMIT = 200
KEEPALIVE_SECONDS = 15.0
TAILER_POLL_CONCURRENCY = 8
_TAILER_POLL_SEMAPHORE = asyncio.Semaphore(TAILER_POLL_CONCURRENCY)


WorkspacePath = Annotated[
    UUID,
    Path(
        description="Workspace identifier",
        alias="workspaceId",
    ),
]
ClientRequestIdHeader = Annotated[str | None, Header(alias="X-Client-Request-Id")]
DocumentPath = Annotated[
    UUID,
    Path(
        description="Document identifier",
        alias="documentId",
    ),
]
DocumentsServiceDep = Annotated[DocumentsService, Depends(get_documents_service)]
RunsServiceDep = Annotated[RunsService, Depends(get_runs_service)]
DocumentReader = Annotated[
    User,
    Security(
        require_workspace("workspace.documents.read"),
        scopes=["{workspaceId}"],
    ),
]
DocumentManager = Annotated[
    User,
    Security(
        require_workspace("workspace.documents.manage"),
        scopes=["{workspaceId}"],
    ),
]


def _resolve_change_cursor(request: Request, cursor: str | None) -> int:
    last_event_id = request.headers.get("last-event-id") or request.headers.get("Last-Event-ID")
    tokens: list[str] = []
    if cursor is not None:
        tokens.append(cursor)
    if last_event_id is not None:
        tokens.append(last_event_id)
    if not tokens:
        return 0
    try:
        values = [int(token) for token in tokens]
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="cursor must be an integer string",
        ) from exc
    return max(values)


def _parse_metadata(metadata: str | None) -> dict[str, Any]:
    if metadata is None:
        return {}
    candidate = metadata.strip()
    if not candidate:
        return {}
    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError as exc:  # pragma: no cover - validation guard
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="metadata must be valid JSON",
        ) from exc
    if not isinstance(decoded, dict):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="metadata must be a JSON object",
        )
    return decoded


def _parse_run_options(run_options: str | None) -> DocumentUploadRunOptions | None:
    if run_options is None:
        return None
    candidate = run_options.strip()
    if not candidate:
        return None
    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError as exc:  # pragma: no cover - validation guard
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="run_options must be valid JSON",
        ) from exc
    if not isinstance(decoded, dict):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="run_options must be a JSON object",
        )
    try:
        return DocumentUploadRunOptions.model_validate(decoded)
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=exc.errors(),
        ) from exc


def _try_enqueue_run(
    *,
    runs_service: RunsService,
    workspace_id: UUID,
    document_id: UUID,
    run_options: DocumentUploadRunOptions | None = None,
) -> None:
    try:
        if runs_service.is_processing_paused(workspace_id=workspace_id):
            return
        options = None
        if run_options:
            options = RunCreateOptionsBase(
                input_sheet_names=run_options.input_sheet_names,
                active_sheet_only=run_options.active_sheet_only,
            )
        runs_service.prepare_run_for_workspace(
            workspace_id=workspace_id,
            input_document_id=document_id,
            configuration_id=None,
            options=options,
        )
    except ConfigurationNotFoundError:
        return
    except RunQueueFullError as exc:
        logger.warning(
            "document.auto_run.queue_full",
            extra=log_context(workspace_id=workspace_id, document_id=document_id, detail=str(exc)),
        )
    except Exception:
        logger.exception(
            "document.auto_run.failed",
            extra=log_context(workspace_id=workspace_id, document_id=document_id),
        )


@router.post(
    "",
    dependencies=[Security(require_csrf)],
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    response_model_exclude_none=True,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Metadata payload or expiration timestamp is invalid.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to upload documents.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document uploads.",
        },
        status.HTTP_413_CONTENT_TOO_LARGE: {
            "description": "Uploaded file exceeds the configured size limit.",
        },
    },
)
def upload_document(
    workspace_id: WorkspacePath,
    service: DocumentsServiceDep,
    runs_service: RunsServiceDep,
    request: Request,
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    idempotency: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    _actor: DocumentManager,
    *,
    file: Annotated[UploadFile, File(...)],
    metadata: Annotated[str | None, Form()] = None,
    expires_at: Annotated[str | None, Form()] = None,
    run_options: Annotated[str | None, Form()] = None,
) -> DocumentOut:
    upload_slot_acquired = False
    upload_semaphore = getattr(request.app.state, "documents_upload_semaphore", None)
    if upload_semaphore is not None:
        upload_slot_acquired = upload_semaphore.acquire(blocking=False)
        if not upload_slot_acquired:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many concurrent uploads. Please retry shortly.",
            )
    payload = _parse_metadata(metadata)
    upload_run_options = _parse_run_options(run_options)
    metadata_payload = service.build_upload_metadata(payload, upload_run_options)
    staged = None
    scope_key = build_scope_key(
        principal_id=str(_actor.id),
        workspace_id=str(workspace_id),
    )
    try:
        staged = service.stage_upload(workspace_id=workspace_id, upload=file)
        request_hash = build_request_hash(
            method=request.method,
            path=request.url.path,
            payload={
                "metadata": metadata_payload,
                "expires_at": expires_at,
                "run_options": upload_run_options.model_dump() if upload_run_options else None,
                "filename": file.filename,
                "content_type": file.content_type,
                "file_sha256": staged.stored.sha256,
                "file_size": staged.stored.byte_size,
            },
        )
        replay = idempotency.resolve_replay(
            key=idempotency_key,
            scope_key=scope_key,
            request_hash=request_hash,
        )
        if replay:
            service.discard_staged_upload(workspace_id=workspace_id, staged=staged)
            return replay.to_response()
        document = service.create_document(
            workspace_id=workspace_id,
            upload=file,
            metadata=metadata_payload,
            expires_at=expires_at,
            actor=_actor,
            staged=staged,
        )
    except DocumentTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
    except InvalidDocumentExpirationError as exc:
        if staged is not None:
            service.discard_staged_upload(workspace_id=workspace_id, staged=staged)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        if staged is not None:
            service.discard_staged_upload(workspace_id=workspace_id, staged=staged)
        raise
    finally:
        if upload_slot_acquired:
            upload_semaphore.release()

    _try_enqueue_run(
        runs_service=runs_service,
        workspace_id=workspace_id,
        document_id=document.id,
        run_options=upload_run_options,
    )

    idempotency.store_response(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
        status_code=status.HTTP_201_CREATED,
        body=document,
    )
    return document


@router.get(
    "",
    response_model=DocumentListPage,
    status_code=status.HTTP_200_OK,
    summary="List documents",
    response_model_exclude_none=True,
    dependencies=[Depends(strict_list_query_guard())],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list documents.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document access.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Query parameters are invalid or unsupported.",
        },
    },
)
def list_documents(
    workspace_id: WorkspacePath,
    list_query: Annotated[ListQueryParams, Depends(list_query_params)],
    service: DocumentsServiceDep,
    response: Response,
    actor: DocumentReader,
) -> DocumentListPage:
    order_by = resolve_sort(
        list_query.sort,
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    page_result = service.list_documents(
        workspace_id=workspace_id,
        page=list_query.page,
        per_page=list_query.per_page,
        order_by=order_by,
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
    )
    response.headers["X-Ade-Changes-Cursor"] = page_result.changes_cursor
    return page_result


@router.get(
    "/changes",
    response_model=DocumentChangesPage,
    status_code=status.HTTP_200_OK,
    summary="List document changes",
    response_model_exclude_none=True,
    dependencies=[Depends(strict_list_query_guard(allowed_extra={"cursor", "limit", "includeRows"}))],
)
def list_document_changes(
    workspace_id: WorkspacePath,
    service: DocumentsServiceDep,
    _actor: DocumentReader,
    *,
    cursor: Annotated[str | None, Query(description="Cursor token.")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    include_rows: Annotated[bool, Query(alias="includeRows")] = False,
) -> DocumentChangesPage:
    if cursor is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="cursor is required",
        )
    try:
        page = service.list_document_changes(
            workspace_id=workspace_id,
            cursor_token=cursor,
            limit=limit,
            include_rows=include_rows,
        )
        return DocumentChangesPage(items=page.items, next_cursor=page.next_cursor)
    except DocumentEventCursorTooOld as exc:
        raise HTTPException(
            status.HTTP_410_GONE,
            detail={
                "error": "resync_required",
                "oldestCursor": str(exc.oldest_cursor),
                "latestCursor": str(exc.latest_cursor),
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/changes/stream",
    summary="Stream document changes",
)
async def stream_document_changes(
    workspace_id: WorkspacePath,
    request: Request,
    settings: SettingsDep,
    _actor: DocumentReader,
    *,
    cursor: Annotated[str | None, Query(description="Cursor token.")] = None,
    include_rows: Annotated[bool, Query(alias="includeRows")] = False,
) -> EventSourceResponse:
    start_cursor = _resolve_change_cursor(request, cursor)
    session_factory = get_sessionmaker(request)

    async def event_stream():
        cursor_value = start_cursor
        last_send = time.monotonic()
        poll_interval = TAILER_POLL_INTERVAL_SECONDS

        def _resolve_cursor() -> int:
            with session_factory() as session:
                events_service = DocumentEventsService(session=session, settings=settings)
                resolution = events_service.resolve_cursor(
                    workspace_id=workspace_id,
                    cursor=cursor_value,
                )
                return resolution.cursor

        try:
            cursor_value = await asyncio.to_thread(_resolve_cursor)
        except DocumentEventCursorTooOld as exc:
            yield sse_json(
                "error",
                {
                    "code": "resync_required",
                    "oldestCursor": str(exc.oldest_cursor),
                    "latestCursor": str(exc.latest_cursor),
                },
            )
            return

        yield sse_json("ready", {"cursor": str(cursor_value)})

        while True:
            if await request.is_disconnected():
                return

            def _fetch_changes(current_cursor: int):
                with session_factory() as session:
                    events_service = DocumentEventsService(session=session, settings=settings)
                    events = events_service.fetch_changes_after(
                        workspace_id=workspace_id,
                        cursor=current_cursor,
                        limit=TAILER_BATCH_LIMIT,
                    )
                    service = DocumentsService(session=session, settings=settings)
                    return service.build_change_entries(
                        workspace_id=workspace_id,
                        events=events,
                        include_rows=include_rows,
                    )

            async with _TAILER_POLL_SEMAPHORE:
                events = await asyncio.to_thread(_fetch_changes, cursor_value)

            if events:
                poll_interval = TAILER_POLL_INTERVAL_SECONDS
                for change in events:
                    payload = change.model_dump(by_alias=True, exclude_none=True)
                    yield sse_json(change.type, payload, event_id=change.cursor)
                    cursor_value = int(change.cursor)
                    last_send = time.monotonic()
                continue

            now = time.monotonic()
            if now - last_send >= KEEPALIVE_SECONDS:
                last_send = now
                yield sse_json("keepalive", {})

            poll_interval = min(TAILER_POLL_MAX_INTERVAL_SECONDS, poll_interval * 1.5)
            await asyncio.sleep(poll_interval)

    return EventSourceResponse(
        event_stream(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.patch(
    "/{documentId}",
    dependencies=[Security(require_csrf)],
    response_model=DocumentOut,
    status_code=status.HTTP_200_OK,
    summary="Update document metadata or assignment",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to update documents.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document updates.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
        },
    },
)
def update_document(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    payload: DocumentUpdateRequest,
    request: Request,
    response: Response,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentOut:
    try:
        current = service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        require_if_match(
            request.headers.get("if-match"),
            expected_token=build_etag_token(current.id, current.version),
        )
        updated = service.update_document(
            workspace_id=workspace_id,
            document_id=document_id,
            payload=payload,
            client_request_id=client_request_id,
        )
        etag = format_weak_etag(build_etag_token(updated.id, updated.version))
        if etag:
            response.headers["ETag"] = etag
        return updated
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/batch/tags",
    dependencies=[Security(require_csrf)],
    response_model=DocumentBatchTagsResponse,
    status_code=status.HTTP_200_OK,
    summary="Update tags on multiple documents",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to update tags.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document updates.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "One or more documents were not found within the workspace.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Tag payload is invalid.",
        },
    },
)
def patch_document_tags_batch(
    workspace_id: WorkspacePath,
    payload: DocumentBatchTagsRequest,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentBatchTagsResponse:
    try:
        documents = service.patch_document_tags_batch(
            workspace_id=workspace_id,
            document_ids=payload.document_ids,
            add=payload.add,
            remove=payload.remove,
            client_request_id=client_request_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidDocumentTagsError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    return DocumentBatchTagsResponse(documents=documents)


@router.post(
    "/batch/archive",
    dependencies=[Security(require_csrf)],
    response_model=DocumentBatchArchiveResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive multiple documents",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to update documents.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document updates.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "One or more documents were not found within the workspace.",
        },
    },
)
def archive_documents_batch_endpoint(
    workspace_id: WorkspacePath,
    payload: DocumentBatchArchiveRequest,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentBatchArchiveResponse:
    try:
        documents = service.archive_documents_batch(
            workspace_id=workspace_id,
            document_ids=payload.document_ids,
            client_request_id=client_request_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return DocumentBatchArchiveResponse(documents=documents)


@router.post(
    "/batch/restore",
    dependencies=[Security(require_csrf)],
    response_model=DocumentBatchArchiveResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore multiple documents from the archive",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to update documents.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document updates.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "One or more documents were not found within the workspace.",
        },
    },
)
def restore_documents_batch_endpoint(
    workspace_id: WorkspacePath,
    payload: DocumentBatchArchiveRequest,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentBatchArchiveResponse:
    try:
        documents = service.restore_documents_batch(
            workspace_id=workspace_id,
            document_ids=payload.document_ids,
            client_request_id=client_request_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return DocumentBatchArchiveResponse(documents=documents)


@router.post(
    "/{documentId}/archive",
    dependencies=[Security(require_csrf)],
    response_model=DocumentOut,
    status_code=status.HTTP_200_OK,
    summary="Archive a document",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to update documents.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document updates.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
        },
    },
)
def archive_document_endpoint(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    request: Request,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentOut:
    try:
        current = service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        require_if_match(
            request.headers.get("if-match"),
            expected_token=build_etag_token(current.id, current.version),
        )
        return service.archive_document(
            workspace_id=workspace_id,
            document_id=document_id,
            client_request_id=client_request_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{documentId}/restore",
    dependencies=[Security(require_csrf)],
    response_model=DocumentOut,
    status_code=status.HTTP_200_OK,
    summary="Restore a document from the archive",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to update documents.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document updates.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
        },
    },
)
def restore_document_endpoint(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    request: Request,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentOut:
    try:
        current = service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        require_if_match(
            request.headers.get("if-match"),
            expected_token=build_etag_token(current.id, current.version),
        )
        return service.restore_document(
            workspace_id=workspace_id,
            document_id=document_id,
            client_request_id=client_request_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put(
    "/{documentId}/tags",
    dependencies=[Security(require_csrf)],
    response_model=DocumentOut,
    status_code=status.HTTP_200_OK,
    summary="Replace document tags",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to update tags.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document updates.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Tag payload is invalid.",
        },
    },
)
def replace_document_tags(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    payload: DocumentTagsReplace,
    request: Request,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentOut:
    try:
        current = service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        require_if_match(
            request.headers.get("if-match"),
            expected_token=build_etag_token(current.id, current.version),
        )
        return service.replace_document_tags(
            workspace_id=workspace_id,
            document_id=document_id,
            tags=payload.tags,
            client_request_id=client_request_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidDocumentTagsError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.patch(
    "/{documentId}/tags",
    dependencies=[Security(require_csrf)],
    response_model=DocumentOut,
    status_code=status.HTTP_200_OK,
    summary="Update document tags",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to update tags.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document updates.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Tag payload is invalid.",
        },
    },
)
def patch_document_tags(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    payload: DocumentTagsPatch,
    request: Request,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentOut:
    try:
        current = service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        require_if_match(
            request.headers.get("if-match"),
            expected_token=build_etag_token(current.id, current.version),
        )
        return service.patch_document_tags(
            workspace_id=workspace_id,
            document_id=document_id,
            add=payload.add,
            remove=payload.remove,
            client_request_id=client_request_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidDocumentTagsError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get(
    "/{documentId}",
    response_model=DocumentOut,
    status_code=status.HTTP_200_OK,
    summary="Retrieve document metadata",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to access documents.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document access.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
        },
    },
)
def read_document(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    response: Response,
    service: DocumentsServiceDep,
    _actor: DocumentReader,
) -> DocumentOut:
    try:
        document = service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        etag = format_weak_etag(build_etag_token(document.id, document.version))
        if etag:
            response.headers["ETag"] = etag
        return document
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{documentId}/listrow",
    response_model=DocumentListRow,
    status_code=status.HTTP_200_OK,
    summary="Retrieve document list row",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to access documents.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document access.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
        },
    },
)
def read_document_list_row(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    service: DocumentsServiceDep,
    _actor: DocumentReader,
) -> DocumentListRow:
    try:
        return service.get_document_list_row(
            workspace_id=workspace_id,
            document_id=document_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{documentId}/download",
    summary="Download a stored document",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to download documents.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document downloads.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document is missing or its stored file is unavailable.",
        },
    },
)
def download_document(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    request: Request,
    settings: SettingsDep,
    _actor: DocumentReader,
) -> StreamingResponse:
    session_factory = get_sessionmaker(request)
    try:
        with session_factory() as session:
            service = DocumentsService(session=session, settings=settings)
            record, stream = service.stream_document(
                workspace_id=workspace_id,
                document_id=document_id,
            )
            media_type = record.content_type or "application/octet-stream"
            disposition = build_content_disposition(record.name)
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentFileMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    response = StreamingResponse(stream, media_type=media_type)
    response.headers["Content-Disposition"] = disposition
    return response


@router.get(
    "/{documentId}/preview",
    response_model=WorkbookSheetPreview,
    summary="Preview a document worksheet",
    response_model_exclude_none=True,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
        },
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {
            "description": "Preview is not supported for this file type.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "The workbook exists but could not be parsed for preview.",
        },
    },
)
def preview_document(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    service: DocumentsServiceDep,
    _actor: DocumentReader,
    *,
    max_rows: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_PREVIEW_ROWS,
            alias="maxRows",
            description="Maximum rows per sheet to include in the preview.",
        ),
    ] = DEFAULT_PREVIEW_ROWS,
    max_columns: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_PREVIEW_COLUMNS,
            alias="maxColumns",
            description="Maximum columns per sheet to include in the preview.",
        ),
    ] = DEFAULT_PREVIEW_COLUMNS,
    trim_empty_columns: Annotated[
        bool,
        Query(
            alias="trimEmptyColumns",
            description="If true, trims columns with no data within the preview window.",
        ),
    ] = False,
    trim_empty_rows: Annotated[
        bool,
        Query(
            alias="trimEmptyRows",
            description="If true, trims rows with no data within the preview window.",
        ),
    ] = False,
    sheet_name: Annotated[
        str | None,
        Query(
            alias="sheetName",
            description=(
                "Optional worksheet name to preview "
                "(defaults to the first sheet when omitted)."
            ),
        ),
    ] = None,
    sheet_index: Annotated[
        int | None,
        Query(
            ge=0,
            alias="sheetIndex",
            description=(
                "Optional worksheet index to preview "
                "(0-based, defaults to the first sheet when omitted)."
            ),
        ),
    ] = None,
) -> WorkbookSheetPreview:
    if sheet_name and sheet_index is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="sheetName and sheetIndex are mutually exclusive",
        )
    if sheet_name is None and sheet_index is None:
        sheet_index = 0
    try:
        return service.get_document_preview(
            workspace_id=workspace_id,
            document_id=document_id,
            max_rows=max_rows,
            max_columns=max_columns,
            trim_empty_columns=trim_empty_columns,
            trim_empty_rows=trim_empty_rows,
            sheet_name=sheet_name,
            sheet_index=sheet_index,
        )
    except (DocumentNotFoundError, DocumentFileMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentPreviewUnsupportedError as exc:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except (DocumentPreviewParseError, DocumentPreviewSheetNotFoundError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get(
    "/{documentId}/sheets",
    response_model=list[DocumentSheet],
    summary="List worksheets for a document",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "The workbook exists but could not be parsed for worksheets.",
        },
    },
)
def list_document_sheets_endpoint(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    service: DocumentsServiceDep,
    _actor: DocumentReader,
) -> list[DocumentSheet]:
    try:
        return service.list_document_sheets(
            workspace_id=workspace_id,
            document_id=document_id,
        )
    except (DocumentNotFoundError, DocumentFileMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentWorksheetParseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.delete(
    "/{documentId}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a document",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to delete documents.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document deletion.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
        },
    },
)
def delete_document(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    request: Request,
    service: DocumentsServiceDep,
    actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> None:
    try:
        current = service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        require_if_match(
            request.headers.get("if-match"),
            expected_token=build_etag_token(current.id, current.version),
        )
        service.delete_document(
            workspace_id=workspace_id,
            document_id=document_id,
            actor=actor,
            client_request_id=client_request_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/batch/delete",
    dependencies=[Security(require_csrf)],
    response_model=DocumentBatchDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Soft delete multiple documents",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to delete documents.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document deletion.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "One or more documents were not found within the workspace.",
        },
    },
)
def delete_documents_batch(
    workspace_id: WorkspacePath,
    payload: DocumentBatchDeleteRequest,
    service: DocumentsServiceDep,
    actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentBatchDeleteResponse:
    try:
        deleted_ids = service.delete_documents_batch(
            workspace_id=workspace_id,
            document_ids=payload.document_ids,
            actor=actor,
            client_request_id=client_request_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return DocumentBatchDeleteResponse(document_ids=deleted_ids)


@tags_router.get(
    "/tags",
    response_model=TagCatalogPage,
    status_code=status.HTTP_200_OK,
    summary="List document tags",
    response_model_exclude_none=True,
    dependencies=[Depends(strict_list_query_guard())],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list tags.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow tag access.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Tag search parameters are invalid.",
        },
    },
)
def list_document_tags(
    workspace_id: WorkspacePath,
    list_query: Annotated[ListQueryParams, Depends(list_query_params)],
    service: DocumentsServiceDep,
    _actor: DocumentReader,
) -> TagCatalogPage:
    try:
        if list_query.filters:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Tag listings do not support filters.",
            )
        return service.list_tag_catalog(
            workspace_id=workspace_id,
            page=list_query.page,
            per_page=list_query.per_page,
            q=list_query.q,
            sort=list_query.sort,
        )
    except InvalidDocumentTagsError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


__all__ = ["router", "tags_router"]
