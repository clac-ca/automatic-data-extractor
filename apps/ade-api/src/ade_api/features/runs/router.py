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

from ade_api.api.deps import (
    get_runs_service,
)
from ade_api.common.downloads import build_content_disposition
from ade_api.common.encoding import json_bytes
from ade_api.common.events import EventRecord, strip_sequence
from ade_api.common.pagination import PageParams
from ade_api.common.sorting import make_sort_dependency
from ade_api.common.sse import sse_json
from ade_api.common.types import OrderBy
from ade_api.core.http import require_authenticated, require_csrf
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.models import RunStatus

from .exceptions import (
    RunDocumentMissingError,
    RunInputMissingError,
    RunLogsFileMissingError,
    RunNotFoundError,
    RunOutputMissingError,
    RunOutputNotReadyError,
    RunQueueFullError,
)
from .filters import RunColumnFilters, RunFilters
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

get_sort_order = make_sort_dependency(
    allowed=SORT_FIELDS,
    default=DEFAULT_SORT,
    id_field=ID_FIELD,
)

_FILTER_KEYS = {
    "q",
    "status",
    "input_document_id",
    "created_after",
    "created_before",
    "file_type",
    "has_output",
}

_COLUMN_FILTER_KEYS = {
    "sheet_name",
    "sheet_index",
    "table_index",
    "mapped_field",
    "mapping_status",
}


def get_run_filters(
    request: Request,
    filters: Annotated[RunFilters, Depends()],
) -> RunFilters:
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
    return filters


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
    "/configurations/{configuration_id}/runs",
    response_model=RunResource,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
async def create_run_endpoint(
    *,
    configuration_id: Annotated[UUID, Path(description="Configuration identifier")],
    payload: RunCreateRequest,
    service: RunsService = runs_service_dependency,
) -> RunResource:
    """Create a run for ``configuration_id`` and enqueue execution."""

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
    return resource


@router.post(
    "/configurations/{configuration_id}/runs/batch",
    response_model=RunBatchCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
async def create_runs_batch_endpoint(
    *,
    configuration_id: Annotated[UUID, Path(description="Configuration identifier")],
    payload: RunBatchCreateRequest,
    service: RunsService = runs_service_dependency,
) -> RunBatchCreateResponse:
    """Create multiple runs for ``configuration_id`` and enqueue execution."""

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
    return RunBatchCreateResponse(runs=resources)


@router.post(
    "/workspaces/{workspace_id}/runs",
    response_model=RunResource,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
async def create_workspace_run_endpoint(
    *,
    workspace_id: Annotated[UUID, Path(description="Workspace identifier")],
    payload: RunWorkspaceCreateRequest,
    service: RunsService = runs_service_dependency,
) -> RunResource:
    """Create a run for ``workspace_id`` and enqueue execution."""

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
    return resource


@router.post(
    "/workspaces/{workspace_id}/runs/batch",
    response_model=RunBatchCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
async def create_workspace_runs_batch_endpoint(
    *,
    workspace_id: Annotated[UUID, Path(description="Workspace identifier")],
    payload: RunWorkspaceBatchCreateRequest,
    service: RunsService = runs_service_dependency,
) -> RunBatchCreateResponse:
    """Create multiple runs for ``workspace_id`` and enqueue execution."""

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
    return RunBatchCreateResponse(runs=resources)


@router.get(
    "/configurations/{configuration_id}/runs",
    response_model=RunPage,
    response_model_exclude_none=True,
)
async def list_configuration_runs_endpoint(
    configuration_id: Annotated[UUID, Path(description="Configuration identifier")],
    page: Annotated[PageParams, Depends()],
    filters: Annotated[RunFilters, Depends(get_run_filters)],
    order_by: Annotated[OrderBy, Depends(get_sort_order)],
    service: RunsService = runs_service_dependency,
) -> RunPage:
    try:
        return await service.list_runs_for_configuration(
            configuration_id=configuration_id,
            filters=filters,
            order_by=order_by,
            page=page.page,
            page_size=page.page_size,
            include_total=page.include_total,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/workspaces/{workspace_id}/runs",
    response_model=RunPage,
    response_model_exclude_none=True,
)
async def list_workspace_runs_endpoint(
    workspace_id: Annotated[UUID, Path(description="Workspace identifier")],
    page: Annotated[PageParams, Depends()],
    filters: Annotated[RunFilters, Depends(get_run_filters)],
    order_by: Annotated[OrderBy, Depends(get_sort_order)],
    service: RunsService = runs_service_dependency,
) -> RunPage:
    return await service.list_runs(
        workspace_id=workspace_id,
        filters=filters,
        order_by=order_by,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )


@router.get("/runs/{run_id}", response_model=RunResource)
async def get_run_endpoint(
    run_id: Annotated[UUID, Path(description="Run identifier")],
    service: RunsService = runs_service_dependency,
) -> RunResource:
    run = await service.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run not found")
    return await service.to_resource(run)


@router.get(
    "/runs/{run_id}/metrics",
    response_model=RunMetricsResource,
    response_model_exclude_none=True,
)
async def get_run_metrics_endpoint(
    run_id: Annotated[UUID, Path(description="Run identifier")],
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
    "/runs/{run_id}/fields",
    response_model=list[RunFieldResource],
    response_model_exclude_none=True,
)
async def list_run_fields_endpoint(
    run_id: Annotated[UUID, Path(description="Run identifier")],
    service: RunsService = runs_service_dependency,
) -> list[RunFieldResource]:
    try:
        fields = await service.list_run_fields(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [RunFieldResource.model_validate(item) for item in fields]


@router.get(
    "/runs/{run_id}/columns",
    response_model=list[RunColumnResource],
    response_model_exclude_none=True,
)
async def list_run_columns_endpoint(
    run_id: Annotated[UUID, Path(description="Run identifier")],
    filters: Annotated[RunColumnFilters, Depends(get_run_column_filters)],
    service: RunsService = runs_service_dependency,
) -> list[RunColumnResource]:
    try:
        columns = await service.list_run_columns(run_id=run_id, filters=filters)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [RunColumnResource.model_validate(item) for item in columns]


@router.get(
    "/runs/{run_id}/input",
    response_model=RunInput,
    response_model_exclude_none=True,
    summary="Get run input metadata",
)
async def get_run_input_endpoint(
    run_id: Annotated[UUID, Path(description="Run identifier")],
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
    "/runs/{run_id}/input/download",
    summary="Download run input file",
)
async def download_run_input_endpoint(
    run_id: Annotated[UUID, Path(description="Run identifier")],
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
    "/runs/{run_id}/events",
    response_model=RunEventsPage,
    response_model_exclude_none=True,
)
async def get_run_events_endpoint(
    run_id: Annotated[UUID, Path(description="Run identifier")],
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


@router.get("/runs/{run_id}/events/stream")
async def stream_run_events_endpoint(
    run_id: Annotated[UUID, Path(description="Run identifier")],
    request: Request,
    after_sequence: int | None = Query(default=None, ge=0),
    service: RunsService = runs_service_dependency,
) -> StreamingResponse:
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

    async def event_stream() -> AsyncIterator[bytes]:
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

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/runs/{run_id}/events/download",
    response_class=FileResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Events unavailable"}},
    summary="Download run events (NDJSON log)",
)
async def download_run_events_file_endpoint(
    run_id: Annotated[UUID, Path(description="Run identifier")],
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
    "/runs/{run_id}/output",
    response_model=RunOutput,
    response_model_exclude_none=True,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Run or output not found"},
    },
    summary="Get run output metadata",
)
async def get_run_output_metadata_endpoint(
    run_id: Annotated[UUID, Path(description="Run identifier")],
    service: RunsService = runs_service_dependency,
) -> RunOutput:
    try:
        return await service.get_run_output_metadata(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/runs/{run_id}/output/download",
    response_class=FileResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Output not found"},
        status.HTTP_409_CONFLICT: {"description": "Output not ready"},
    },
    summary="Download run output file",
)
async def download_run_output_endpoint(
    run_id: Annotated[UUID, Path(description="Run identifier")],
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
