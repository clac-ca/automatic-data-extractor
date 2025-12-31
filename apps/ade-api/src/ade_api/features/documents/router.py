from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal
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
from sse_starlette.sse import EventSourceResponse
from pydantic import ValidationError
from ade_api.api.deps import get_documents_service, get_runs_service
from ade_api.common.downloads import build_content_disposition
from ade_api.common.logging import log_context
from ade_api.common.pagination import PageParams
from ade_api.common.sse import sse_json
from ade_api.common.sorting import make_sort_dependency
from ade_api.common.types import OrderBy
from ade_api.core.http import require_authenticated, require_csrf, require_workspace
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.runs.schemas import RunCreateOptionsBase
from ade_api.features.runs.exceptions import RunQueueFullError
from ade_api.features.runs.service import RunsService
from ade_api.models import User

from .change_feed import DocumentChangeCursorTooOld
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
from .filters import DocumentFilters
from .schemas import (
    DocumentBatchArchiveRequest,
    DocumentBatchArchiveResponse,
    DocumentBatchDeleteRequest,
    DocumentBatchDeleteResponse,
    DocumentBatchTagsRequest,
    DocumentBatchTagsResponse,
    DocumentChangesPage,
    DocumentOut,
    DocumentPage,
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
    prefix="/workspaces/{workspace_id}/documents",
    tags=["documents"],
    dependencies=[Security(require_authenticated)],
)
tags_router = APIRouter(
    prefix="/workspaces/{workspace_id}",
    tags=["documents"],
    dependencies=[Security(require_authenticated)],
)

logger = logging.getLogger(__name__)


WorkspacePath = Annotated[
    UUID,
    Path(
        description="Workspace identifier",
    ),
]
DocumentPath = Annotated[
    UUID,
    Path(
        description="Document identifier",
    ),
]
DocumentsServiceDep = Annotated[DocumentsService, Depends(get_documents_service)]
RunsServiceDep = Annotated[RunsService, Depends(get_runs_service)]
DocumentReader = Annotated[
    User,
    Security(
        require_workspace("workspace.documents.read"),
        scopes=["{workspace_id}"],
    ),
]
DocumentManager = Annotated[
    User,
    Security(
        require_workspace("workspace.documents.manage"),
        scopes=["{workspace_id}"],
    ),
]


get_sort_order = make_sort_dependency(
    allowed=SORT_FIELDS,
    default=DEFAULT_SORT,
    id_field=ID_FIELD,
)

_FILTER_KEYS = {
    "q",
    "status",
    "status_in",
    "display_status",
    "display_status_in",
    "run_status",
    "source_in",
    "tags",
    "tag_mode",
    "tags_match",
    "tags_not",
    "tags_empty",
    "uploader",
    "uploader_id",
    "uploader_id_in",
    "uploader_email",
    "assignee_user_id",
    "assignee_user_id_in",
    "assignee_unassigned",
    "folder_id",
    "created_after",
    "created_before",
    "updated_after",
    "updated_before",
    "created_at_from",
    "created_at_to",
    "last_run_from",
    "last_run_to",
    "activity_after",
    "activity_before",
    "activity_at_from",
    "activity_at_to",
    "byte_size_from",
    "byte_size_to",
    "file_type",
    "has_output",
}


def get_document_filters(
    request: Request,
) -> DocumentFilters:
    allowed = _FILTER_KEYS
    allowed_with_shared = allowed | {"sort", "page", "page_size", "include_total"}
    extras = sorted({key for key in request.query_params.keys() if key not in allowed_with_shared})
    if extras:
        detail = [
            {
                "type": "extra_forbidden",
                "loc": ["query", key],
                "msg": "Extra inputs are not permitted",
                "input": request.query_params.get(key),
            }
            for key in extras
        ]
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)

    data: dict[str, object] = {}
    for key in allowed:
        values = request.query_params.getlist(key)
        if not values:
            continue
        data[key] = values if len(values) > 1 else values[0]

    try:
        return DocumentFilters.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(),
        ) from exc


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

    return document


@router.get(
    "",
    response_model=DocumentPage,
    status_code=status.HTTP_200_OK,
    summary="List documents",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list documents.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document access.",
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Query parameters are invalid or unsupported.",
        },
    },
)
async def list_documents(
    workspace_id: WorkspacePath,
    page: Annotated[PageParams, Depends()],
    filters: Annotated[DocumentFilters, Depends(get_document_filters)],
    order_by: Annotated[OrderBy, Depends(get_sort_order)],
    service: DocumentsServiceDep,
    response: Response,
    actor: DocumentReader,
) -> DocumentPage:
    page_result = await service.list_documents(
        workspace_id=workspace_id,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
        order_by=order_by,
        filters=filters,
        actor=actor,
    )
    response.headers["X-Ade-Changes-Cursor"] = page_result.changes_cursor
    return page_result


@router.get(
    "/changes",
    response_model=DocumentChangesPage,
    status_code=status.HTTP_200_OK,
    summary="List document changes",
    response_model_exclude_none=True,
)
async def list_document_changes(
    workspace_id: WorkspacePath,
    service: DocumentsServiceDep,
    _actor: DocumentReader,
    *,
    cursor: Annotated[str | None, Query(description="Cursor token or 'latest'.")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> DocumentChangesPage:
    if cursor is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="cursor is required; use cursor=latest to sync from now",
        )
    try:
        return await service.list_document_changes(
            workspace_id=workspace_id,
            cursor_token=cursor,
            limit=limit,
        )
    except DocumentChangeCursorTooOld as exc:
        raise HTTPException(
            status.HTTP_410_GONE,
            detail={"error": "resync_required", "latest_cursor": str(exc.latest_cursor)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/changes/stream")
async def stream_document_changes(
    workspace_id: WorkspacePath,
    request: Request,
    service: DocumentsServiceDep,
    _actor: DocumentReader,
    *,
    cursor: Annotated[str | None, Query(description="Cursor token or 'latest'.")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> EventSourceResponse:
    last_event_id = request.headers.get("Last-Event-ID") or request.headers.get("last-event-id")
    if last_event_id and cursor and last_event_id != cursor:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="cursor and Last-Event-ID must match when both are provided",
        )
    start_token = last_event_id or cursor or "latest"

    try:
        initial_page = await service.list_document_changes(
            workspace_id=workspace_id,
            cursor_token=start_token,
            limit=limit,
        )
    except DocumentChangeCursorTooOld as exc:
        raise HTTPException(
            status.HTTP_410_GONE,
            detail={"error": "resync_required", "latest_cursor": str(exc.latest_cursor)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    async def event_stream() -> AsyncIterator[dict[str, str]]:
        base_interval = 2.0
        max_interval = 30.0
        backoff = 1.6
        jitter_ratio = 0.2
        poll_interval = base_interval

        cursor_value = 0
        pending = initial_page.changes
        if start_token != "latest":
            try:
                cursor_value = int(start_token)
            except (TypeError, ValueError):
                cursor_value = 0
        if start_token == "latest":
            cursor_value = int(initial_page.next_cursor)

        while True:
            if pending:
                for change in pending:
                    cursor_value = int(change.cursor)
                    yield sse_json(
                        change.type,
                        change.model_dump(),
                        event_id=change.cursor,
                    )
                pending = []
                continue

            if await request.is_disconnected():
                return

            try:
                page = await service.list_document_changes(
                    workspace_id=workspace_id,
                    cursor_token=str(cursor_value),
                    limit=limit,
                )
            except DocumentChangeCursorTooOld:
                return

            if page.changes:
                pending = page.changes
                poll_interval = base_interval
                continue

            jitter = poll_interval * jitter_ratio
            delay = max(0.0, poll_interval + random.uniform(-jitter, jitter))
            await asyncio.sleep(delay)
            poll_interval = min(max_interval, poll_interval * backoff)

    return EventSourceResponse(
        event_stream(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
        ping=15,
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
    "/uploadSessions/{upload_session_id}",
    dependencies=[Security(require_csrf)],
    response_model=DocumentUploadSessionUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a byte range to a session",
    response_model_exclude_none=True,
)
async def upload_session_range(
    workspace_id: WorkspacePath,
    upload_session_id: Annotated[UUID, Path(description="Upload session identifier")],
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
    "/uploadSessions/{upload_session_id}",
    response_model=DocumentUploadSessionStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get upload session status",
    response_model_exclude_none=True,
)
async def get_upload_session_status(
    workspace_id: WorkspacePath,
    upload_session_id: Annotated[UUID, Path(description="Upload session identifier")],
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
    "/uploadSessions/{upload_session_id}/commit",
    dependencies=[Security(require_csrf)],
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Commit an upload session",
    response_model_exclude_none=True,
)
async def commit_upload_session(
    workspace_id: WorkspacePath,
    upload_session_id: Annotated[UUID, Path(description="Upload session identifier")],
    service: DocumentsServiceDep,
    runs_service: RunsServiceDep,
    actor: DocumentManager,
) -> DocumentOut:
    try:
        document, upload_run_options = await service.commit_upload_session(
            workspace_id=workspace_id,
            upload_session_id=upload_session_id,
            actor=actor,
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

    return document


@router.delete(
    "/uploadSessions/{upload_session_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel an upload session",
)
async def cancel_upload_session(
    workspace_id: WorkspacePath,
    upload_session_id: Annotated[UUID, Path(description="Upload session identifier")],
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
    "/{document_id}",
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
    service: DocumentsServiceDep,
    _actor: DocumentManager,
) -> DocumentOut:
    try:
        return await service.update_document(
            workspace_id=workspace_id,
            document_id=document_id,
            payload=payload,
        )
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
) -> DocumentBatchTagsResponse:
    try:
        documents = await service.patch_document_tags_batch(
            workspace_id=workspace_id,
            document_ids=payload.document_ids,
            add=payload.add,
            remove=payload.remove,
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
) -> DocumentBatchArchiveResponse:
    try:
        documents = await service.archive_documents_batch(
            workspace_id=workspace_id,
            document_ids=payload.document_ids,
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
) -> DocumentBatchArchiveResponse:
    try:
        documents = await service.restore_documents_batch(
            workspace_id=workspace_id,
            document_ids=payload.document_ids,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return DocumentBatchArchiveResponse(documents=documents)


@router.post(
    "/{document_id}/archive",
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
    service: DocumentsServiceDep,
    _actor: DocumentManager,
) -> DocumentOut:
    try:
        return await service.archive_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{document_id}/restore",
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
    service: DocumentsServiceDep,
    _actor: DocumentManager,
) -> DocumentOut:
    try:
        return await service.restore_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put(
    "/{document_id}/tags",
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
    service: DocumentsServiceDep,
    _actor: DocumentManager,
) -> DocumentOut:
    try:
        return await service.replace_document_tags(
            workspace_id=workspace_id,
            document_id=document_id,
            tags=payload.tags,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidDocumentTagsError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.patch(
    "/{document_id}/tags",
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
    service: DocumentsServiceDep,
    _actor: DocumentManager,
) -> DocumentOut:
    try:
        return await service.patch_document_tags(
            workspace_id=workspace_id,
            document_id=document_id,
            add=payload.add,
            remove=payload.remove,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidDocumentTagsError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.get(
    "/{document_id}",
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
    service: DocumentsServiceDep,
    _actor: DocumentReader,
) -> DocumentOut:
    try:
        return await service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{document_id}/download",
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

    media_type = record.content_type or "application/octet-stream"
    response = StreamingResponse(stream, media_type=media_type)
    response.headers["Content-Disposition"] = build_content_disposition(record.name)
    return response


@router.get(
    "/{document_id}/sheets",
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
    "/{document_id}",
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
    service: DocumentsServiceDep,
    actor: DocumentManager,
) -> None:
    try:
        await service.delete_document(
            workspace_id=workspace_id,
            document_id=document_id,
            actor=actor,
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
) -> DocumentBatchDeleteResponse:
    try:
        deleted_ids = await service.delete_documents_batch(
            workspace_id=workspace_id,
            document_ids=payload.document_ids,
            actor=actor,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return DocumentBatchDeleteResponse(document_ids=deleted_ids)


TagCatalogSort = Literal["name", "-count"]


@tags_router.get(
    "/tags",
    response_model=TagCatalogPage,
    status_code=status.HTTP_200_OK,
    summary="List document tags",
    response_model_exclude_none=True,
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
    page: Annotated[PageParams, Depends()],
    service: DocumentsServiceDep,
    _actor: DocumentReader,
    *,
    q: Annotated[str | None, Query(description="Search tags (min length 2).")] = None,
    sort: Annotated[TagCatalogSort, Query()] = "name",
) -> TagCatalogPage:
    try:
        return await service.list_tag_catalog(
            workspace_id=workspace_id,
            page=page.page,
            page_size=page.page_size,
            include_total=page.include_total,
            q=q,
            sort=sort,
        )
    except InvalidDocumentTagsError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


__all__ = ["router", "tags_router"]
