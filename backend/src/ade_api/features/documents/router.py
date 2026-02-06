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
    HTTPException,
    Path,
    Query,
    Request,
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
    get_documents_service_read,
    get_runs_service,
    get_runs_service_read,
)
from ade_api.common.downloads import build_content_disposition
from ade_api.common.cursor_listing import (
    CursorQueryParams,
    cursor_query_params,
    resolve_cursor_sort,
    strict_cursor_query_guard,
)
from ade_api.common.logging import log_context
from ade_api.common.sse import sse_json
from ade_api.common.workbook_preview import (
    DEFAULT_PREVIEW_COLUMNS,
    DEFAULT_PREVIEW_ROWS,
    MAX_PREVIEW_COLUMNS,
    MAX_PREVIEW_ROWS,
    WorkbookSheetPreview,
)
from ade_api.core.http import require_authenticated, require_csrf, require_workspace
from ade_api.db import get_session_factory
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.runs.schemas import RunCreateOptionsBase
from ade_api.features.runs.service import RunsService
from ade_storage import get_storage_adapter
from ade_db.models import User

from .changes import (
    DEFAULT_DELTA_LIMIT,
    MAX_DELTA_LIMIT,
    get_latest_document_change_id,
    parse_document_change_cursor,
)
from .events import get_document_changes_hub
from .exceptions import (
    DocumentFileMissingError,
    DocumentNameConflictError,
    DocumentNotFoundError,
    DocumentPreviewParseError,
    DocumentPreviewSheetNotFoundError,
    DocumentPreviewUnsupportedError,
    DocumentTooLargeError,
    DocumentVersionNotFoundError,
    DocumentWorksheetParseError,
    InvalidDocumentCommentMentionsError,
    InvalidDocumentTagsError,
)
from .schemas import (
    DocumentBatchDeleteRequest,
    DocumentBatchDeleteResponse,
    DocumentBatchTagsRequest,
    DocumentBatchTagsResponse,
    DocumentChangeDeltaResponse,
    DocumentChangeEntry,
    DocumentCommentCreate,
    DocumentCommentOut,
    DocumentCommentPage,
    DocumentConflictMode,
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
from .sorting import (
    COMMENT_CURSOR_FIELDS,
    COMMENT_DEFAULT_SORT,
    COMMENT_ID_FIELD,
    COMMENT_SORT_FIELDS,
    CURSOR_FIELDS,
    DEFAULT_SORT,
    ID_FIELD,
    SORT_FIELDS,
)

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
KEEPALIVE_SECONDS = 15.0

WorkspacePath = Annotated[
    UUID,
    Path(
        description="Workspace identifier",
        alias="workspaceId",
    ),
]
DocumentPath = Annotated[
    UUID,
    Path(
        description="Document identifier",
        alias="documentId",
    ),
]
DocumentsServiceDep = Annotated[DocumentsService, Depends(get_documents_service)]
DocumentsServiceReadDep = Annotated[
    DocumentsService, Depends(get_documents_service_read)
]
RunsServiceDep = Annotated[RunsService, Depends(get_runs_service)]
RunsServiceReadDep = Annotated[RunsService, Depends(get_runs_service_read)]
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


def _resolve_event_token(request: Request, cursor: str | None) -> int | None:
    last_event_id = request.headers.get("last-event-id") or request.headers.get("Last-Event-ID")
    token = last_event_id if last_event_id is not None else cursor
    if token is None:
        return None
    return parse_document_change_cursor(token)


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
) -> bool:
    try:
        if runs_service.is_processing_paused(workspace_id=workspace_id):
            return False
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
        return True
    except ConfigurationNotFoundError:
        return False
    except Exception:
        logger.exception(
            "document.auto_run.failed",
            extra=log_context(workspace_id=workspace_id, document_id=document_id),
        )
    return False


@router.post(
    "",
    dependencies=[Security(require_csrf)],
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    response_model_exclude_none=True,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Metadata payload is invalid.",
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
        status.HTTP_409_CONFLICT: {
            "description": "Document name already exists.",
        },
    },
)
def upload_document(
    workspace_id: WorkspacePath,
    service: DocumentsServiceDep,
    runs_service: RunsServiceDep,
    request: Request,
    _actor: DocumentManager,
    *,
    file: Annotated[UploadFile, File(...)],
    metadata: Annotated[str | None, Form()] = None,
    run_options: Annotated[str | None, Form()] = None,
    conflict_mode: Annotated[DocumentConflictMode | None, Form(alias="conflictMode")] = None,
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
    try:
        plan = service.plan_upload(
            workspace_id=workspace_id,
            filename=file.filename,
            conflict_mode=conflict_mode,
        )
        staged = service.stage_upload(upload=file, plan=plan)
        document = service.create_document(
            workspace_id=workspace_id,
            upload=file,
            plan=plan,
            metadata=metadata_payload,
            actor=_actor,
            staged=staged,
        )
    except DocumentTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
    except DocumentNameConflictError as exc:
        if staged is not None:
            service.discard_staged_upload(staged=staged)
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception:
        if staged is not None:
            service.discard_staged_upload(staged=staged)
        raise
    finally:
        if upload_slot_acquired:
            upload_semaphore.release()

    run_enqueued = _try_enqueue_run(
        runs_service=runs_service,
        workspace_id=workspace_id,
        document_id=document.id,
        run_options=upload_run_options,
    )
    if run_enqueued:
        document = service.get_document(
            workspace_id=workspace_id,
            document_id=document.id,
        )
        document.list_row = service._build_list_row(document)

    return document


@router.post(
    "/{documentId}/versions",
    dependencies=[Security(require_csrf)],
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new document version",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to upload document versions.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document uploads.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
        },
        status.HTTP_413_CONTENT_TOO_LARGE: {
            "description": "Uploaded file exceeds the configured size limit.",
        },
    },
)
def upload_document_version(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    service: DocumentsServiceDep,
    _actor: DocumentManager,
    *,
    file: Annotated[UploadFile, File(...)],
    metadata: Annotated[str | None, Form()] = None,
) -> DocumentOut:
    payload = _parse_metadata(metadata)
    metadata_payload = service.build_upload_metadata(payload, None)
    staged = None
    try:
        plan = service.plan_upload_for_version(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        staged = service.stage_upload(upload=file, plan=plan)
        document = service.create_document(
            workspace_id=workspace_id,
            upload=file,
            plan=plan,
            metadata=metadata_payload,
            actor=_actor,
            staged=staged,
        )
        return document
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
    except Exception:
        if staged is not None:
            service.discard_staged_upload(staged=staged)
        raise


@router.get(
    "",
    response_model=DocumentListPage,
    status_code=status.HTTP_200_OK,
    summary="List documents",
    response_model_exclude_none=True,
    dependencies=[Depends(strict_cursor_query_guard())],
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
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    service: DocumentsServiceReadDep,
    actor: DocumentReader,
    include_run_metrics: Annotated[bool, Query(alias="includeRunMetrics")] = False,
    include_run_table_columns: Annotated[bool, Query(alias="includeRunTableColumns")] = False,
    include_run_fields: Annotated[bool, Query(alias="includeRunFields")] = False,
) -> DocumentListPage:
    resolved_sort = resolve_cursor_sort(
        list_query.sort,
        allowed=SORT_FIELDS,
        cursor_fields=CURSOR_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    page_result = service.list_documents(
        workspace_id=workspace_id,
        limit=list_query.limit,
        cursor=list_query.cursor,
        resolved_sort=resolved_sort,
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        include_total=list_query.include_total,
        include_facets=list_query.include_facets,
        include_run_metrics=include_run_metrics,
        include_run_table_columns=include_run_table_columns,
        include_run_fields=include_run_fields,
    )
    return page_result


@router.get(
    "/stream",
    summary="Stream document changes",
)
async def stream_document_changes(
    workspace_id: WorkspacePath,
    request: Request,
    _actor: DocumentReader,
    *,
    cursor: Annotated[str | None, Query(description="Change cursor.")] = None,
) -> EventSourceResponse:
    start_token = _resolve_event_token(request, cursor)
    session_factory = get_session_factory(request)
    events_hub = get_document_changes_hub(request)

    async def event_stream():
        token_value = start_token
        queue, unsubscribe = events_hub.subscribe(str(workspace_id))

        def _current_token() -> int | None:
            with session_factory() as session:
                return get_latest_document_change_id(session, workspace_id)

        try:
            token_value = await asyncio.to_thread(_current_token)
        except Exception:
            token_value = start_token

        ready_id = str(token_value) if token_value is not None else None
        yield sse_json("ready", {"lastId": ready_id})

        try:
            while True:
                if await request.is_disconnected():
                    return

                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    yield sse_json("keepalive", {})
                    continue

                payload = dict(payload)
                op = payload.get("op")
                document_id = payload.get("documentId")
                change_id = payload.get("id")
                if not op or not document_id:
                    continue
                event_type = "document.deleted" if op == "delete" else "document.changed"
                event_id = change_id
                yield sse_json(
                    event_type,
                    {"documentId": document_id, "op": op, "id": change_id},
                    event_id=event_id,
                )
        finally:
            unsubscribe()

    return EventSourceResponse(
        event_stream(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/delta",
    response_model=DocumentChangeDeltaResponse,
    status_code=status.HTTP_200_OK,
    summary="List document changes since token",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to read document changes.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document access.",
        },
        status.HTTP_410_GONE: {
            "description": "Change cursor expired; refresh the document list.",
        },
    },
)
def list_document_changes_delta(
    workspace_id: WorkspacePath,
    service: DocumentsServiceReadDep,
    _actor: DocumentReader,
    *,
    since: Annotated[str, Query(description="Change cursor.")],
    limit: Annotated[int, Query(ge=1, le=MAX_DELTA_LIMIT)] = DEFAULT_DELTA_LIMIT,
) -> DocumentChangeDeltaResponse:
    start = time.perf_counter()
    since_id = parse_document_change_cursor(since)
    delta = service.get_document_change_delta(
        workspace_id=workspace_id,
        since=since_id,
        limit=limit,
    )
    changes = [
        DocumentChangeEntry(
            id=str(change.id),
            document_id=change.document_id,
            op=change.op,
        )
        for change in delta.changes
    ]
    response = DocumentChangeDeltaResponse(
        changes=changes,
        next_since=str(delta.next_since),
        has_more=delta.has_more,
    )
    duration_ms = (time.perf_counter() - start) * 1000.0
    logger.info(
        "documents.delta.success",
        extra={
            "workspace_id": str(workspace_id),
            "count": len(changes),
            "duration_ms": round(duration_ms, 2),
            "has_more": delta.has_more,
        },
    )
    return response


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
    service: DocumentsServiceDep,
    _actor: DocumentManager,
) -> DocumentOut:
    try:
        updated = service.update_document(
            workspace_id=workspace_id,
            document_id=document_id,
            payload=payload,
        )
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
) -> DocumentBatchTagsResponse:
    try:
        documents = service.patch_document_tags_batch(
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
    service: DocumentsServiceDep,
    _actor: DocumentManager,
) -> DocumentOut:
    try:
        return service.replace_document_tags(
            workspace_id=workspace_id,
            document_id=document_id,
            tags=payload.tags,
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
    service: DocumentsServiceDep,
    _actor: DocumentManager,
) -> DocumentOut:
    try:
        return service.patch_document_tags(
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
    service: DocumentsServiceReadDep,
    _actor: DocumentReader,
    include_run_metrics: Annotated[bool, Query(alias="includeRunMetrics")] = False,
    include_run_table_columns: Annotated[bool, Query(alias="includeRunTableColumns")] = False,
    include_run_fields: Annotated[bool, Query(alias="includeRunFields")] = False,
    ) -> DocumentOut:
    try:
        document = service.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
            include_run_metrics=include_run_metrics,
            include_run_table_columns=include_run_table_columns,
            include_run_fields=include_run_fields,
        )
        return document
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{documentId}/listrow",
    response_model=DocumentListRow,
    status_code=status.HTTP_200_OK,
    summary="Retrieve document list row",
    response_model_exclude_none=False,
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
    service: DocumentsServiceReadDep,
    _actor: DocumentReader,
    include_run_metrics: Annotated[bool, Query(alias="includeRunMetrics")] = False,
    include_run_table_columns: Annotated[bool, Query(alias="includeRunTableColumns")] = False,
    include_run_fields: Annotated[bool, Query(alias="includeRunFields")] = False,
) -> DocumentListRow:
    try:
        return service.get_document_list_row(
            workspace_id=workspace_id,
            document_id=document_id,
            include_run_metrics=include_run_metrics,
            include_run_table_columns=include_run_table_columns,
            include_run_fields=include_run_fields,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{documentId}/comments",
    response_model=DocumentCommentPage,
    status_code=status.HTTP_200_OK,
    summary="List document comments",
    response_model_exclude_none=False,
    dependencies=[Depends(strict_cursor_query_guard())],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to access comments.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document access.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
        },
    },
)
def list_document_comments(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    service: DocumentsServiceReadDep,
    _actor: DocumentReader,
) -> DocumentCommentPage:
    try:
        resolved_sort = resolve_cursor_sort(
            list_query.sort,
            allowed=COMMENT_SORT_FIELDS,
            cursor_fields=COMMENT_CURSOR_FIELDS,
            default=COMMENT_DEFAULT_SORT,
            id_field=COMMENT_ID_FIELD,
        )
        return service.list_document_comments(
            workspace_id=workspace_id,
            document_id=document_id,
            limit=list_query.limit,
            cursor=list_query.cursor,
            resolved_sort=resolved_sort,
            include_total=list_query.include_total,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{documentId}/comments",
    dependencies=[Security(require_csrf)],
    response_model=DocumentCommentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a document comment",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to create comments.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document access.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document not found within the workspace.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Comment payload is invalid.",
        },
    },
)
def create_document_comment(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    payload: DocumentCommentCreate,
    service: DocumentsServiceDep,
    actor: DocumentReader,
) -> DocumentCommentOut:
    try:
        return service.create_document_comment(
            workspace_id=workspace_id,
            document_id=document_id,
            body=payload.body,
            mentions=payload.mentions,
            actor=actor,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidDocumentCommentMentionsError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


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
    blob_storage = get_storage_adapter(request)
    session_factory = get_session_factory(request)
    try:
        with session_factory() as session:
            service = DocumentsService(
                session=session,
                settings=settings,
                storage=blob_storage,
            )
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
    "/{documentId}/versions/{versionNo}/download",
    summary="Download a specific document version",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to download documents.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow document downloads.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Document or version not found within the workspace.",
        },
    },
)
def download_document_version(
    workspace_id: WorkspacePath,
    document_id: DocumentPath,
    version_no: Annotated[int, Path(alias="versionNo", ge=1)],
    request: Request,
    settings: SettingsDep,
    _actor: DocumentReader,
) -> StreamingResponse:
    blob_storage = get_storage_adapter(request)
    session_factory = get_session_factory(request)
    try:
        with session_factory() as session:
            service = DocumentsService(
                session=session,
                settings=settings,
                storage=blob_storage,
            )
            record, version, stream = service.stream_document_version(
                workspace_id=workspace_id,
                document_id=document_id,
                version_no=version_no,
            )
            media_type = (
                version.content_type
                or record.content_type
                or "application/octet-stream"
            )
            filename = version.filename_at_upload or record.name
            disposition = build_content_disposition(filename)
    except DocumentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentVersionNotFoundError as exc:
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
    service: DocumentsServiceReadDep,
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
    service: DocumentsServiceReadDep,
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
    service: DocumentsServiceDep,
    actor: DocumentManager,
) -> None:
    try:
        service.delete_document(
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
def delete_documents_batch(
    workspace_id: WorkspacePath,
    payload: DocumentBatchDeleteRequest,
    service: DocumentsServiceDep,
    actor: DocumentManager,
) -> DocumentBatchDeleteResponse:
    try:
        deleted_ids = service.delete_documents_batch(
            workspace_id=workspace_id,
            document_ids=payload.document_ids,
            actor=actor,
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
    dependencies=[Depends(strict_cursor_query_guard())],
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
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    service: DocumentsServiceReadDep,
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
            limit=list_query.limit,
            cursor=list_query.cursor,
            include_total=list_query.include_total,
            q=list_query.q,
            sort=list_query.sort,
        )
    except InvalidDocumentTagsError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


__all__ = ["router", "tags_router"]
