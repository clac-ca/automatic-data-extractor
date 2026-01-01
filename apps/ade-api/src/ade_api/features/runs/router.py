"""FastAPI router exposing ADE run APIs."""

from __future__ import annotations

import logging
import mimetypes
from collections.abc import AsyncIterator
from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    Security,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from ade_api.api.deps import get_idempotency_service, get_runs_service
from ade_api.common.downloads import build_content_disposition
from ade_api.common.encoding import json_bytes
from ade_api.common.events import EventRecord, strip_sequence
from ade_api.common.listing import (
    ListQueryParams,
    list_query_params,
    strict_list_query_guard,
)
from ade_api.common.sorting import resolve_sort
from ade_api.common.sse import sse_json
from ade_api.common.workbook_preview import (
    DEFAULT_PREVIEW_COLUMNS,
    DEFAULT_PREVIEW_ROWS,
    MAX_PREVIEW_COLUMNS,
    MAX_PREVIEW_ROWS,
    WorkbookPreview,
)
from ade_api.core.auth import AuthenticatedPrincipal
from ade_api.core.http import get_current_principal, require_authenticated, require_csrf
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.idempotency import (
    IdempotencyService,
    build_request_hash,
    build_scope_key,
    require_idempotency_key,
)
from ade_api.models import RunStatus

from .exceptions import (
    RunDocumentMissingError,
    RunInputMissingError,
    RunLogsFileMissingError,
    RunNotFoundError,
    RunOutputMissingError,
    RunOutputNotReadyError,
    RunOutputPreviewParseError,
    RunOutputPreviewSheetNotFoundError,
    RunOutputPreviewUnsupportedError,
    RunQueueFullError,
)
from .filters import RunColumnFilters
from .schemas import (
    RunBatchCreateRequest,
    RunBatchCreateResponse,
    RunColumnResource,
    RunCreateRequest,
    RunEventsPage,
    RunFieldResource,
    RunInput,
    RunMetricsResource,
    RunOutput,
    RunPage,
    RunResource,
    RunWorkspaceBatchCreateRequest,
    RunWorkspaceCreateRequest,
)
from .service import (
    DEFAULT_EVENTS_PAGE_LIMIT,
    RunsService,
)
from .sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS

router = APIRouter(
    tags=["runs"],
    dependencies=[Security(require_authenticated)],
)
runs_service_dependency = Depends(get_runs_service)
logger = logging.getLogger(__name__)

WorkspacePath = Annotated[
    UUID,
    Path(
        description="Workspace identifier",
        alias="workspaceId",
    ),
]
ConfigurationPath = Annotated[
    UUID,
    Path(
        description="Configuration identifier",
        alias="configurationId",
    ),
]
RunPath = Annotated[
    UUID,
    Path(
        description="Run identifier",
        alias="runId",
    ),
]

_COLUMN_FILTER_KEYS = {
    "sheet_name",
    "sheet_index",
    "table_index",
    "mapped_field",
    "mapping_status",
}


def get_run_column_filters(
    request: Request,
    filters: Annotated[RunColumnFilters, Depends()],
) -> RunColumnFilters:
    allowed = _COLUMN_FILTER_KEYS
    extras = sorted({key for key in request.query_params.keys() if key not in allowed})
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
    return filters


def _event_bytes(event: EventRecord) -> bytes:
    return json_bytes(event) + b"\n"



@router.post(
    "/configurations/{configurationId}/runs",
    response_model=RunResource,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
async def create_run_endpoint(
    *,
    configuration_id: ConfigurationPath,
    payload: RunCreateRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    idempotency: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    service: RunsService = runs_service_dependency,
) -> RunResource:
    """Create a run for ``configuration_id`` and enqueue execution."""

    scope_key = build_scope_key(principal_id=str(principal.user_id))
    request_hash = build_request_hash(
        method=request.method,
        path=request.url.path,
        payload=payload,
    )
    replay = await idempotency.resolve_replay(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
    )
    if replay:
        return replay.to_response()

    try:
        run = await service.prepare_run(
            configuration_id=configuration_id,
            options=payload.options,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunInputMissingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RunQueueFullError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "run_queue_full",
                    "message": str(exc),
                }
            },
        ) from exc

    resource = await service.to_resource(run)
    await idempotency.store_response(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
        status_code=status.HTTP_201_CREATED,
        body=resource,
    )
    return resource


@router.post(
    "/configurations/{configurationId}/runs/batch",
    response_model=RunBatchCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
async def create_runs_batch_endpoint(
    *,
    configuration_id: ConfigurationPath,
    payload: RunBatchCreateRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    idempotency: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    service: RunsService = runs_service_dependency,
) -> RunBatchCreateResponse:
    """Create multiple runs for ``configuration_id`` and enqueue execution."""

    scope_key = build_scope_key(principal_id=str(principal.user_id))
    request_hash = build_request_hash(
        method=request.method,
        path=request.url.path,
        payload=payload,
    )
    replay = await idempotency.resolve_replay(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
    )
    if replay:
        return replay.to_response()

    try:
        runs = await service.prepare_runs_batch(
            configuration_id=configuration_id,
            document_ids=payload.document_ids,
            options=payload.options,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunQueueFullError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "run_queue_full",
                    "message": str(exc),
                }
            },
        ) from exc

    resources = [await service.to_resource(run) for run in runs]
    response_payload = RunBatchCreateResponse(runs=resources)
    await idempotency.store_response(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
        status_code=status.HTTP_201_CREATED,
        body=response_payload,
    )
    return response_payload


@router.post(
    "/workspaces/{workspaceId}/runs",
    response_model=RunResource,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
async def create_workspace_run_endpoint(
    *,
    workspace_id: WorkspacePath,
    payload: RunWorkspaceCreateRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    idempotency: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    service: RunsService = runs_service_dependency,
) -> RunResource:
    """Create a run for ``workspace_id`` and enqueue execution."""

    scope_key = build_scope_key(
        principal_id=str(principal.user_id),
        workspace_id=str(workspace_id),
    )
    request_hash = build_request_hash(
        method=request.method,
        path=request.url.path,
        payload=payload,
    )
    replay = await idempotency.resolve_replay(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
    )
    if replay:
        return replay.to_response()

    try:
        run = await service.prepare_run_for_workspace(
            workspace_id=workspace_id,
            configuration_id=payload.configuration_id,
            input_document_id=payload.input_document_id,
            options=payload.options,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunInputMissingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RunQueueFullError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "run_queue_full",
                    "message": str(exc),
                }
            },
        ) from exc

    resource = await service.to_resource(run)
    await idempotency.store_response(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
        status_code=status.HTTP_201_CREATED,
        body=resource,
    )
    return resource


@router.post(
    "/workspaces/{workspaceId}/runs/batch",
    response_model=RunBatchCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
async def create_workspace_runs_batch_endpoint(
    *,
    workspace_id: WorkspacePath,
    payload: RunWorkspaceBatchCreateRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    idempotency: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    service: RunsService = runs_service_dependency,
) -> RunBatchCreateResponse:
    """Create multiple runs for ``workspace_id`` and enqueue execution."""

    scope_key = build_scope_key(
        principal_id=str(principal.user_id),
        workspace_id=str(workspace_id),
    )
    request_hash = build_request_hash(
        method=request.method,
        path=request.url.path,
        payload=payload,
    )
    replay = await idempotency.resolve_replay(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
    )
    if replay:
        return replay.to_response()

    try:
        runs = await service.prepare_runs_batch_for_workspace(
            workspace_id=workspace_id,
            configuration_id=payload.configuration_id,
            document_ids=payload.document_ids,
            options=payload.options,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunQueueFullError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "run_queue_full",
                    "message": str(exc),
                }
            },
        ) from exc

    resources = [await service.to_resource(run) for run in runs]
    response_payload = RunBatchCreateResponse(runs=resources)
    await idempotency.store_response(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
        status_code=status.HTTP_201_CREATED,
        body=response_payload,
    )
    return response_payload


@router.get(
    "/configurations/{configurationId}/runs",
    response_model=RunPage,
    response_model_exclude_none=True,
)
async def list_configuration_runs_endpoint(
    configuration_id: ConfigurationPath,
    list_query: Annotated[ListQueryParams, Depends(list_query_params)],
    _guard: Annotated[None, Depends(strict_list_query_guard())],
    service: RunsService = runs_service_dependency,
) -> RunPage:
    try:
        order_by = resolve_sort(
            list_query.sort,
            allowed=SORT_FIELDS,
            default=DEFAULT_SORT,
            id_field=ID_FIELD,
        )
        return await service.list_runs_for_configuration(
            configuration_id=configuration_id,
            filters=list_query.filters,
            join_operator=list_query.join_operator,
            q=list_query.q,
            order_by=order_by,
            page=list_query.page,
            per_page=list_query.per_page,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/workspaces/{workspaceId}/runs",
    response_model=RunPage,
    response_model_exclude_none=True,
)
async def list_workspace_runs_endpoint(
    workspace_id: WorkspacePath,
    list_query: Annotated[ListQueryParams, Depends(list_query_params)],
    _guard: Annotated[None, Depends(strict_list_query_guard())],
    service: RunsService = runs_service_dependency,
) -> RunPage:
    order_by = resolve_sort(
        list_query.sort,
        allowed=SORT_FIELDS,
        default=DEFAULT_SORT,
        id_field=ID_FIELD,
    )
    return await service.list_runs(
        workspace_id=workspace_id,
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        order_by=order_by,
        page=list_query.page,
        per_page=list_query.per_page,
    )


@router.get("/runs/{runId}", response_model=RunResource)
async def get_run_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
) -> RunResource:
    run = await service.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run not found")
    return await service.to_resource(run)


@router.get(
    "/runs/{runId}/metrics",
    response_model=RunMetricsResource,
    response_model_exclude_none=True,
)
async def get_run_metrics_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
) -> RunMetricsResource:
    try:
        metrics = await service.get_run_metrics(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if metrics is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run metrics not available")
    return RunMetricsResource.model_validate(metrics)


@router.get(
    "/runs/{runId}/fields",
    response_model=list[RunFieldResource],
    response_model_exclude_none=True,
)
async def list_run_fields_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
) -> list[RunFieldResource]:
    try:
        fields = await service.list_run_fields(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [RunFieldResource.model_validate(item) for item in fields]


@router.get(
    "/runs/{runId}/columns",
    response_model=list[RunColumnResource],
    response_model_exclude_none=True,
)
async def list_run_columns_endpoint(
    run_id: RunPath,
    filters: Annotated[RunColumnFilters, Depends(get_run_column_filters)],
    service: RunsService = runs_service_dependency,
) -> list[RunColumnResource]:
    try:
        columns = await service.list_run_columns(run_id=run_id, filters=filters)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [RunColumnResource.model_validate(item) for item in columns]


@router.get(
    "/runs/{runId}/input",
    response_model=RunInput,
    response_model_exclude_none=True,
    summary="Get run input metadata",
)
async def get_run_input_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
) -> RunInput:
    try:
        return await service.get_run_input_metadata(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunInputMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/runs/{runId}/input/download",
    summary="Download run input file",
)
async def download_run_input_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
) -> StreamingResponse:
    try:
        run, document, stream = await service.stream_run_input(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (RunDocumentMissingError, RunInputMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    media_type = document.content_type or "application/octet-stream"
    response = StreamingResponse(stream, media_type=media_type)
    disposition = document.original_filename
    response.headers["Content-Disposition"] = disposition
    return response


@router.get(
    "/runs/{runId}/events",
    response_model=RunEventsPage,
    response_model_exclude_none=True,
)
async def get_run_events_endpoint(
    run_id: RunPath,
    format: Literal["json", "ndjson"] = Query(default="json"),
    after_sequence: int | None = Query(default=None, ge=0),
    limit: int = Query(default=DEFAULT_EVENTS_PAGE_LIMIT, ge=1, le=DEFAULT_EVENTS_PAGE_LIMIT),
    service: RunsService = runs_service_dependency,
) -> RunEventsPage | StreamingResponse:
    try:
        events, next_after_sequence = await service.get_run_events(
            run_id=run_id,
            after_sequence=after_sequence,
            limit=limit,
        )
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if format == "ndjson":

        async def event_stream() -> AsyncIterator[bytes]:
            for event in events:
                yield _event_bytes(event)

        return StreamingResponse(event_stream(), media_type="application/x-ndjson")

    return RunEventsPage(
        items=events,
        next_after_sequence=next_after_sequence,
    )


@router.get("/runs/{runId}/events/stream")
async def stream_run_events_endpoint(
    run_id: RunPath,
    request: Request,
    after_sequence: int | None = Query(default=None, ge=0),
    service: RunsService = runs_service_dependency,
) -> EventSourceResponse:
    run = await service.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run not found")

    last_event_id_header = request.headers.get("last-event-id") or request.headers.get(
        "Last-Event-ID"
    )
    start_sequence = after_sequence
    if start_sequence is None and last_event_id_header:
        try:
            start_sequence = int(last_event_id_header)
        except ValueError:
            start_sequence = None
    start_sequence = start_sequence or 0

    async def event_stream() -> AsyncIterator[dict[str, str]]:
        last_sequence = start_sequence

        async with service.subscribe_to_events(run) as subscription:
            for event in service.iter_events(run=run, after_sequence=start_sequence):
                seq = event.get("sequence")
                if isinstance(seq, int):
                    last_sequence = seq
                else:
                    last_sequence += 1
                payload = strip_sequence(event)
                yield sse_json(
                    str(event.get("event") or "message"),
                    payload,
                    event_id=last_sequence,
                )
                if event.get("event") == "run.complete":
                    return

            run_already_finished = run.status in {
                RunStatus.SUCCEEDED,
                RunStatus.FAILED,
                RunStatus.CANCELLED,
            }
            if run_already_finished:
                return

            async for live_event in subscription:
                seq = live_event.get("sequence")
                if isinstance(seq, int):
                    if seq <= last_sequence:
                        continue
                    last_sequence = seq
                else:
                    last_sequence += 1
                payload = strip_sequence(live_event)
                yield sse_json(
                    str(live_event.get("event") or "message"),
                    payload,
                    event_id=last_sequence,
                )
                if live_event.get("event") == "run.complete":
                    break

    return EventSourceResponse(
        event_stream(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
        ping=15,
    )


@router.get(
    "/runs/{runId}/events/download",
    response_class=FileResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Events unavailable"}},
    summary="Download run events (NDJSON log)",
)
async def download_run_events_file_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
):
    try:
        path = await service.get_logs_file_path(run_id=run_id)
    except (RunNotFoundError, RunLogsFileMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(
        path=path,
        media_type="application/x-ndjson",
        filename=path.name,
        headers={"Content-Disposition": build_content_disposition(path.name)},
    )


@router.get(
    "/runs/{runId}/output",
    response_model=RunOutput,
    response_model_exclude_none=True,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Run or output not found"},
    },
    summary="Get run output metadata",
)
async def get_run_output_metadata_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
) -> RunOutput:
    try:
        return await service.get_run_output_metadata(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/runs/{runId}/output/download",
    response_class=FileResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Output not found"},
        status.HTTP_409_CONFLICT: {"description": "Output not ready"},
    },
    summary="Download run output file",
)
async def download_run_output_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
):
    try:
        run, path = await service.resolve_output_for_download(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunOutputNotReadyError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "OUTPUT_NOT_READY",
                    "message": str(exc),
                }
            },
        ) from exc
    except RunOutputMissingError as exc:
        status_code = status.HTTP_404_NOT_FOUND
        run_record = await service.get_run(run_id)  # type: ignore[arg-type]
        if run_record and run_record.status is RunStatus.FAILED:
            detail = {
                "error": {
                    "code": "RUN_FAILED_NO_OUTPUT",
                    "message": str(exc),
                }
            }
        else:
            detail = str(exc)
        raise HTTPException(status_code, detail=detail) from exc

    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(
        path=path,
        media_type=media_type,
        filename=path.name,
        headers={"Content-Disposition": build_content_disposition(path.name)},
    )


@router.get(
    "/runs/{runId}/output/preview",
    response_model=WorkbookPreview,
    response_model_exclude_none=True,
    summary="Preview run output workbook",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Run or output not found"},
        status.HTTP_409_CONFLICT: {"description": "Output not ready"},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {
            "description": "Preview is not supported for this file type.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "The output exists but could not be parsed for preview.",
        },
    },
)
async def preview_run_output_endpoint(
    run_id: RunPath,
    service: RunsService = runs_service_dependency,
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
    sheet_name: Annotated[
        str | None,
        Query(alias="sheetName", description="Optional worksheet name to preview."),
    ] = None,
    sheet_index: Annotated[
        int | None,
        Query(
            ge=0,
            alias="sheetIndex",
            description="Optional worksheet index to preview (0-based).",
        ),
    ] = None,
) -> WorkbookPreview:
    if sheet_name and sheet_index is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="sheetName and sheetIndex are mutually exclusive",
        )
    try:
        return await service.get_run_output_preview(
            run_id=run_id,
            max_rows=max_rows,
            max_columns=max_columns,
            sheet_name=sheet_name,
            sheet_index=sheet_index,
        )
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunOutputNotReadyError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "OUTPUT_NOT_READY",
                    "message": str(exc),
                }
            },
        ) from exc
    except RunOutputMissingError as exc:
        status_code = status.HTTP_404_NOT_FOUND
        run_record = await service.get_run(run_id)  # type: ignore[arg-type]
        if run_record and run_record.status is RunStatus.FAILED:
            detail = {
                "error": {
                    "code": "RUN_FAILED_NO_OUTPUT",
                    "message": str(exc),
                }
            }
        else:
            detail = str(exc)
        raise HTTPException(status_code, detail=detail) from exc
    except RunOutputPreviewUnsupportedError as exc:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except (RunOutputPreviewParseError, RunOutputPreviewSheetNotFoundError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
