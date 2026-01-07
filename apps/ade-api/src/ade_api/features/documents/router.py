from __future__ import annotations

import asyncio
import hashlib
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
    SessionDep,
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
from ade_api.common.sse import sse_json
from ade_api.common.sorting import resolve_sort
from ade_api.common.workbook_preview import (
    DEFAULT_PREVIEW_COLUMNS,
    DEFAULT_PREVIEW_ROWS,
    MAX_PREVIEW_COLUMNS,
    MAX_PREVIEW_ROWS,
    WorkbookSheetPreview,
)
from ade_api.core.http import require_authenticated, require_csrf, require_workspace
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
from ade_api.db import db
from ade_api.models import User

from .change_feed import DocumentEventCursorTooOld, DocumentEventsService
from .exceptions import (
    DocumentFileMissingError,
    DocumentNotFoundError,
    DocumentPreviewParseError,
    DocumentPreviewSheetNotFoundError,
    DocumentPreviewUnsupportedError,
    DocumentTooLargeError,
    DocumentUploadRangeError,
    DocumentUploadSessionExpiredError,
    DocumentUploadSessionNotFoundError,
    DocumentUploadSessionNotReadyError,
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
    DocumentChangeEntry,
    DocumentChangesPage,
    DocumentListPage,
    DocumentListRow,
    DocumentOut,
    DocumentSheet,
    DocumentTagsPatch,
    DocumentTagsReplace,
    DocumentUpdateRequest,
    DocumentUploadRunOptions,
    DocumentUploadSessionCreateRequest,
    DocumentUploadSessionCreateResponse,
    DocumentUploadSessionStatusResponse,
    DocumentUploadSessionUploadResponse,
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

_UPLOAD_HASH_CHUNK_SIZE = 1024 * 1024
TAILER_POLL_INTERVAL_SECONDS = 0.25
TAILER_BATCH_LIMIT = 200
KEEPALIVE_SECONDS = 15.0


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
UploadSessionPath = Annotated[
    UUID,
    Path(
        description="Upload session identifier",
        alias="uploadSessionId",
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
    token = last_event_id if last_event_id is not None else cursor
    if token is None:
        return 0
    try:
        return int(token)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="cursor must be an integer string") from exc


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


async def _try_enqueue_run(
    *,
    runs_service: RunsService,
    workspace_id: UUID,
    document_id: UUID,
    run_options: DocumentUploadRunOptions | None = None,
) -> None:
    try:
        if await runs_service.is_processing_paused(workspace_id=workspace_id):
            return
        options = None
        if run_options:
            options = RunCreateOptionsBase(
                input_sheet_names=run_options.input_sheet_names,
                active_sheet_only=run_options.active_sheet_only,
            )
        await runs_service.prepare_run_for_workspace(
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


async def _hash_upload_file(upload: UploadFile) -> tuple[str, int]:
    hasher = hashlib.sha256()
    total = 0
    await upload.seek(0)
    while True:
        chunk = await upload.read(_UPLOAD_HASH_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        hasher.update(chunk)
    await upload.seek(0)
    return hasher.hexdigest(), total


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
async def upload_document(
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
    payload = _parse_metadata(metadata)
    upload_run_options = _parse_run_options(run_options)
    metadata_payload = service.build_upload_metadata(payload, upload_run_options)
    file_sha256, file_size = await _hash_upload_file(file)
    scope_key = build_scope_key(
        principal_id=str(_actor.id),
        workspace_id=str(workspace_id),
    )
    request_hash = build_request_hash(
        method=request.method,
        path=request.url.path,
        payload={
            "metadata": metadata_payload,
            "expires_at": expires_at,
            "run_options": upload_run_options.model_dump() if upload_run_options else None,
            "filename": file.filename,
            "content_type": file.content_type,
            "file_sha256": file_sha256,
            "file_size": file_size,
        },
    )
    replay = await idempotency.resolve_replay(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
    )
    if replay:
        return replay.to_response()
    try:
        document = await service.create_document(
            workspace_id=workspace_id,
            upload=file,
            metadata=metadata_payload,
            expires_at=expires_at,
            actor=_actor,
        )
    except DocumentTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
    except InvalidDocumentExpirationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await _try_enqueue_run(
        runs_service=runs_service,
        workspace_id=workspace_id,
        document_id=document.id,
        run_options=upload_run_options,
    )

    await idempotency.store_response(
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
async def list_documents(
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
    page_result = await service.list_documents(
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
    dependencies=[Depends(strict_list_query_guard(allowed_extra={"cursor", "limit"}))],
)
async def list_document_changes(
    workspace_id: WorkspacePath,
    service: DocumentsServiceDep,
    _actor: DocumentReader,
    *,
    cursor: Annotated[str | None, Query(description="Cursor token.")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> DocumentChangesPage:
    if cursor is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="cursor is required",
        )
    try:
        page = await service.list_document_changes(
            workspace_id=workspace_id,
            cursor_token=cursor,
            limit=limit,
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
    db_session: SessionDep,
    _actor: DocumentReader,
    *,
    cursor: Annotated[str | None, Query(description="Cursor token.")] = None,
) -> EventSourceResponse:
    start_cursor = _resolve_change_cursor(request, cursor)
    await db_session.close()

    async def event_stream():
        cursor_value = start_cursor
        last_send = time.monotonic()

        async with db.sessionmaker() as session:
            events_service = DocumentEventsService(session=session, settings=settings)
            oldest_cursor = await events_service.oldest_cursor(workspace_id=workspace_id)
            latest_cursor = await events_service.current_cursor(workspace_id=workspace_id)

        if oldest_cursor is not None and cursor_value < oldest_cursor:
            yield sse_json(
                "error",
                {
                    "code": "resync_required",
                    "oldestCursor": str(oldest_cursor),
                    "latestCursor": str(latest_cursor),
                },
            )
            return

        if cursor_value > latest_cursor:
            cursor_value = latest_cursor

        yield sse_json("ready", {"cursor": str(cursor_value)})

        while True:
            if await request.is_disconnected():
                return

            async with db.sessionmaker() as session:
                events_service = DocumentEventsService(session=session, settings=settings)
                events = await events_service.fetch_changes_after(
                    workspace_id=workspace_id,
                    cursor=cursor_value,
                    limit=TAILER_BATCH_LIMIT,
                )

            if events:
                for change in events:
                    payload = DocumentChangeEntry(
                        cursor=str(change.cursor),
                        type=change.event_type.value,
                        document_id=str(change.document_id),
                        occurred_at=change.occurred_at,
                        document_version=change.document_version,
                        request_id=change.request_id,
                        client_request_id=change.client_request_id,
                    ).model_dump(by_alias=True, exclude_none=True)
                    yield sse_json(change.event_type.value, payload, event_id=change.cursor)
                    cursor_value = int(change.cursor)
                    last_send = time.monotonic()
                continue

            now = time.monotonic()
            if now - last_send >= KEEPALIVE_SECONDS:
                last_send = now
                yield sse_json("keepalive", {})

            await asyncio.sleep(TAILER_POLL_INTERVAL_SECONDS)

    return EventSourceResponse(
        event_stream(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/uploadSessions",
    dependencies=[Security(require_csrf)],
    response_model=DocumentUploadSessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a resumable upload session",
    response_model_exclude_none=True,
)
async def create_upload_session(
    workspace_id: WorkspacePath,
    payload: DocumentUploadSessionCreateRequest,
    service: DocumentsServiceDep,
    actor: DocumentManager,
) -> DocumentUploadSessionCreateResponse:
    try:
        return await service.create_upload_session(
            workspace_id=workspace_id,
            payload=payload,
            actor=actor,
        )
    except DocumentTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc


@router.put(
    "/uploadSessions/{uploadSessionId}",
    dependencies=[Security(require_csrf)],
    response_model=DocumentUploadSessionUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a byte range to a session",
    response_model_exclude_none=True,
)
async def upload_session_range(
    workspace_id: WorkspacePath,
    upload_session_id: UploadSessionPath,
    request: Request,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    content_range: Annotated[str | None, Header(alias="Content-Range")] = None,
) -> DocumentUploadSessionUploadResponse:
    try:
        return await service.upload_session_range(
            workspace_id=workspace_id,
            upload_session_id=upload_session_id,
            content_range=content_range,
            body=request.stream(),
        )
    except DocumentUploadSessionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentUploadSessionExpiredError as exc:
        raise HTTPException(status.HTTP_410_GONE, detail=str(exc)) from exc
    except DocumentUploadRangeError as exc:
        raise HTTPException(
            status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail={
                "detail": str(exc),
                "next_expected_ranges": exc.next_expected_ranges,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/uploadSessions/{uploadSessionId}",
    response_model=DocumentUploadSessionStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get upload session status",
    response_model_exclude_none=True,
)
async def get_upload_session_status(
    workspace_id: WorkspacePath,
    upload_session_id: UploadSessionPath,
    service: DocumentsServiceDep,
    _actor: DocumentReader,
) -> DocumentUploadSessionStatusResponse:
    try:
        return await service.get_upload_session_status(
            workspace_id=workspace_id,
            upload_session_id=upload_session_id,
        )
    except DocumentUploadSessionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentUploadSessionExpiredError as exc:
        raise HTTPException(status.HTTP_410_GONE, detail=str(exc)) from exc


@router.post(
    "/uploadSessions/{uploadSessionId}/commit",
    dependencies=[Security(require_csrf)],
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Commit an upload session",
    response_model_exclude_none=True,
)
async def commit_upload_session(
    workspace_id: WorkspacePath,
    upload_session_id: UploadSessionPath,
    request: Request,
    service: DocumentsServiceDep,
    runs_service: RunsServiceDep,
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    idempotency: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentOut:
    scope_key = build_scope_key(
        principal_id=str(actor.id),
        workspace_id=str(workspace_id),
    )
    request_hash = build_request_hash(
        method=request.method,
        path=request.url.path,
        payload={"upload_session_id": str(upload_session_id)},
    )
    replay = await idempotency.resolve_replay(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
    )
    if replay:
        return replay.to_response()
    try:
        document, upload_run_options = await service.commit_upload_session(
            workspace_id=workspace_id,
            upload_session_id=upload_session_id,
            actor=actor,
            client_request_id=client_request_id,
        )
    except DocumentUploadSessionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentUploadSessionExpiredError as exc:
        raise HTTPException(status.HTTP_410_GONE, detail=str(exc)) from exc
    except DocumentUploadSessionNotReadyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await _try_enqueue_run(
        runs_service=runs_service,
        workspace_id=workspace_id,
        document_id=document.id,
        run_options=upload_run_options,
    )

    await idempotency.store_response(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
        status_code=status.HTTP_201_CREATED,
        body=document,
    )
    return document


@router.delete(
    "/uploadSessions/{uploadSessionId}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel an upload session",
)
async def cancel_upload_session(
    workspace_id: WorkspacePath,
    upload_session_id: UploadSessionPath,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
) -> Response:
    try:
        await service.cancel_upload_session(
            workspace_id=workspace_id,
            upload_session_id=upload_session_id,
        )
    except DocumentUploadSessionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentUploadSessionExpiredError as exc:
        raise HTTPException(status.HTTP_410_GONE, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
async def update_document(
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
        current = await service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        require_if_match(
            request.headers.get("if-match"),
            expected_token=build_etag_token(current.id, current.version),
        )
        updated = await service.update_document(
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
async def patch_document_tags_batch(
    workspace_id: WorkspacePath,
    payload: DocumentBatchTagsRequest,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentBatchTagsResponse:
    try:
        documents = await service.patch_document_tags_batch(
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
async def archive_documents_batch_endpoint(
    workspace_id: WorkspacePath,
    payload: DocumentBatchArchiveRequest,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentBatchArchiveResponse:
    try:
        documents = await service.archive_documents_batch(
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
async def restore_documents_batch_endpoint(
    workspace_id: WorkspacePath,
    payload: DocumentBatchArchiveRequest,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentBatchArchiveResponse:
    try:
        documents = await service.restore_documents_batch(
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
async def archive_document_endpoint(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    request: Request,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentOut:
    try:
        current = await service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        require_if_match(
            request.headers.get("if-match"),
            expected_token=build_etag_token(current.id, current.version),
        )
        return await service.archive_document(
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
async def restore_document_endpoint(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    request: Request,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentOut:
    try:
        current = await service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        require_if_match(
            request.headers.get("if-match"),
            expected_token=build_etag_token(current.id, current.version),
        )
        return await service.restore_document(
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
async def replace_document_tags(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    payload: DocumentTagsReplace,
    request: Request,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentOut:
    try:
        current = await service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        require_if_match(
            request.headers.get("if-match"),
            expected_token=build_etag_token(current.id, current.version),
        )
        return await service.replace_document_tags(
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
async def patch_document_tags(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    payload: DocumentTagsPatch,
    request: Request,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentOut:
    try:
        current = await service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        require_if_match(
            request.headers.get("if-match"),
            expected_token=build_etag_token(current.id, current.version),
        )
        return await service.patch_document_tags(
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
async def read_document(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    response: Response,
    service: DocumentsServiceDep,
    _actor: DocumentReader,
) -> DocumentOut:
    try:
        document = await service.get_document(
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
async def read_document_list_row(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    service: DocumentsServiceDep,
    _actor: DocumentReader,
) -> DocumentListRow:
    try:
        return await service.get_document_list_row(
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
async def download_document(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    service: DocumentsServiceDep,
    db_session: SessionDep,
    _actor: DocumentReader,
) -> StreamingResponse:
    try:
        record, stream = await service.stream_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentFileMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    await db_session.close()
    media_type = record.content_type or "application/octet-stream"
    response = StreamingResponse(stream, media_type=media_type)
    response.headers["Content-Disposition"] = build_content_disposition(record.name)
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
async def preview_document(
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
            description="Optional worksheet name to preview (defaults to the first sheet when omitted).",
        ),
    ] = None,
    sheet_index: Annotated[
        int | None,
        Query(
            ge=0,
            alias="sheetIndex",
            description="Optional worksheet index to preview (0-based, defaults to the first sheet when omitted).",
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
        return await service.get_document_preview(
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
async def list_document_sheets_endpoint(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    service: DocumentsServiceDep,
    _actor: DocumentReader,
) -> list[DocumentSheet]:
    try:
        return await service.list_document_sheets(
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
async def delete_document(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    request: Request,
    service: DocumentsServiceDep,
    actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> None:
    try:
        current = await service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        require_if_match(
            request.headers.get("if-match"),
            expected_token=build_etag_token(current.id, current.version),
        )
        await service.delete_document(
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
async def delete_documents_batch(
    workspace_id: WorkspacePath,
    payload: DocumentBatchDeleteRequest,
    service: DocumentsServiceDep,
    actor: DocumentManager,
    client_request_id: ClientRequestIdHeader = None,
) -> DocumentBatchDeleteResponse:
    try:
        deleted_ids = await service.delete_documents_batch(
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
async def list_document_tags(
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
        return await service.list_tag_catalog(
            workspace_id=workspace_id,
            page=list_query.page,
            per_page=list_query.per_page,
            q=list_query.q,
            sort=list_query.sort,
        )
    except InvalidDocumentTagsError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


__all__ = ["router", "tags_router"]
