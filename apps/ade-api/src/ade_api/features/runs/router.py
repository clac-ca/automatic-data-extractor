"""FastAPI router exposing ADE run APIs."""

from __future__ import annotations

import logging
import mimetypes
from collections.abc import AsyncIterator
from pathlib import Path as FilePath
from typing import Annotated, Any, Literal
from uuid import UUID

from ade_engine.schemas import AdeEvent, RunSummaryV1
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    Security,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse

from ade_api.app.dependencies import (
    get_build_event_dispatcher,
    get_run_event_dispatcher,
    get_runs_service,
)
from ade_api.common.logging import log_context
from ade_api.common.pagination import PageParams
from ade_api.common.ids import UUIDStr
from ade_api.core.http import require_authenticated, require_csrf
from ade_api.core.models import RunStatus
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.infra.db.session import get_sessionmaker
from ade_api.settings import Settings

from .schemas import (
    RunCreateOptions,
    RunCreateRequest,
    RunEventsPage,
    RunFilters,
    RunOutputFile,
    RunOutputListing,
    RunPage,
    RunResource,
)
from .service import (
    DEFAULT_EVENTS_PAGE_LIMIT,
    RunDocumentMissingError,
    RunExecutionContext,
    RunInputMissingError,
    RunLogsFileMissingError,
    RunNotFoundError,
    RunOutputMissingError,
    RunsService,
)

router = APIRouter(
    tags=["runs"],
    dependencies=[Security(require_authenticated)],
)
runs_service_dependency = Depends(get_runs_service)
logger = logging.getLogger(__name__)


async def resolve_run_filters(
    status: Annotated[list[RunStatus] | None, Query()] = None,
    input_document_id: Annotated[UUIDStr | None, Query()] = None,
) -> RunFilters:
    return RunFilters(status=status, input_document_id=input_document_id)


def _event_bytes(event: AdeEvent) -> bytes:
    return event.model_dump_json().encode("utf-8") + b"\n"


def _sse_event_bytes(event: AdeEvent) -> bytes:
    """Format an AdeEvent for SSE with resumable sequence IDs."""

    data = event.model_dump_json()
    lines = data.splitlines() or [""]
    parts: list[str] = []
    if event.sequence is not None:
        parts.append(f"id: {event.sequence}")
    parts.append(f"event: {event.type}")
    parts.extend(f"data: {line}" for line in lines)
    return "\n".join(parts).encode("utf-8") + b"\n\n"


async def _execute_run_background(
    context_data: dict[str, Any],
    options_data: dict[str, Any],
    settings: Settings,
) -> None:
    """Run execution coroutine used for non-streaming requests."""

    session_factory = get_sessionmaker(settings=settings)
    context = RunExecutionContext.from_dict(context_data)
    options = RunCreateOptions(**options_data)
    dispatcher = get_run_event_dispatcher(settings=settings)
    build_dispatcher = get_build_event_dispatcher(settings=settings)
    async with session_factory() as session:
        service = RunsService(
            session=session,
            settings=settings,
            event_dispatcher=dispatcher,
            event_storage=dispatcher.storage,
            build_event_dispatcher=build_dispatcher,
        )
        try:
            await service.run_to_completion(context=context, options=options)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception(
                "run.background.failed",
                extra=log_context(run_id=context.run_id),
            )
            async for event in service.handle_background_failure(
                context=context,
                options=options,
                error=exc,
            ):
                # Force materialization to ensure events are emitted even though we ignore values.
                _ = event


@router.post(
    "/configurations/{configuration_id}/runs",
    response_model=RunResource,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
async def create_run_endpoint(
    *,
    configuration_id: Annotated[UUID, Path(min_length=1, description="Configuration identifier")],
    payload: RunCreateRequest,
    background_tasks: BackgroundTasks,
    service: RunsService = runs_service_dependency,
) -> RunResource:
    """Create a run for ``configuration_id`` and enqueue execution."""

    try:
        run, context = await service.prepare_run(
            configuration_id=configuration_id,
            options=payload.options,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunInputMissingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    resource = service.to_resource(run)
    context_dict = context.as_dict()
    options_dict = payload.options.model_dump()
    background_tasks.add_task(
        _execute_run_background,
        context_dict,
        options_dict,
        service.settings,
    )
    return resource


@router.get(
    "/configurations/{configuration_id}/runs",
    response_model=RunPage,
    response_model_exclude_none=True,
)
async def list_configuration_runs_endpoint(
    configuration_id: Annotated[UUID, Path(min_length=1, description="Configuration identifier")],
    page: Annotated[PageParams, Depends()],
    filters: Annotated[RunFilters, Depends(resolve_run_filters)],
    service: RunsService = runs_service_dependency,
) -> RunPage:
    statuses = [RunStatus(value) for value in filters.status] if filters.status else None
    try:
        return await service.list_runs_for_configuration(
            configuration_id=configuration_id,
            statuses=statuses,
            input_document_id=filters.input_document_id,
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
    workspace_id: Annotated[UUID, Path(min_length=1, description="Workspace identifier")],
    page: Annotated[PageParams, Depends()],
    filters: Annotated[RunFilters, Depends(resolve_run_filters)],
    service: RunsService = runs_service_dependency,
) -> RunPage:
    statuses = [RunStatus(value) for value in filters.status] if filters.status else None
    return await service.list_runs(
        workspace_id=workspace_id,
        statuses=statuses,
        input_document_id=filters.input_document_id,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )


@router.get("/runs/{run_id}", response_model=RunResource)
async def get_run_endpoint(
    run_id: Annotated[UUID, Path(min_length=1, description="Run identifier")],
    service: RunsService = runs_service_dependency,
) -> RunResource:
    run = await service.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run not found")
    return service.to_resource(run)


@router.get(
    "/runs/{run_id}/summary",
    response_model=RunSummaryV1,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Run summary not found"}},
)
async def get_run_summary_endpoint(
    run_id: Annotated[UUID, Path(min_length=1, description="Run identifier")],
    service: RunsService = runs_service_dependency,
) -> RunSummaryV1:
    try:
        summary = await service.get_run_summary(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if summary is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run summary is unavailable")
    return summary


@router.get(
    "/runs/{run_id}/events",
    response_model=RunEventsPage,
    response_model_exclude_none=True,
)
async def get_run_events_endpoint(
    run_id: Annotated[UUID, Path(min_length=1, description="Run identifier")],
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
    run_id: Annotated[UUID, Path(min_length=1, description="Run identifier")],
    request: Request,
    after_sequence: int | None = Query(default=None, ge=0),
    service: RunsService = runs_service_dependency,
) -> StreamingResponse:
    run = await service.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run not found")

    last_event_id_header = request.headers.get("last-event-id") or request.headers.get("Last-Event-ID")
    start_sequence = after_sequence
    if start_sequence is None and last_event_id_header:
        try:
            start_sequence = int(last_event_id_header)
        except ValueError:
            start_sequence = None
    start_sequence = start_sequence or 0

    async def event_stream() -> AsyncIterator[bytes]:
        reader = service.event_log_reader(workspace_id=run.workspace_id, run_id=run.id)
        last_sequence = start_sequence

        for event in reader.iter(after_sequence=start_sequence):
            yield _sse_event_bytes(event)
            if event.sequence:
                last_sequence = event.sequence

        async with service.subscribe_to_events(run.id) as subscription:
            async for live_event in subscription:
                if live_event.sequence and live_event.sequence <= last_sequence:
                    continue
                yield _sse_event_bytes(live_event)
                if live_event.sequence:
                    last_sequence = live_event.sequence

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get(
    "/runs/{run_id}/logs",
    response_class=FileResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Logs unavailable"}},
)
async def download_run_logs_file_endpoint(
    run_id: Annotated[UUID, Path(min_length=1, description="Run identifier")],
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
    )


@router.get(
    "/runs/{run_id}/outputs",
    response_model=RunOutputListing,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Outputs unavailable"}},
)
async def list_run_outputs_endpoint(
    run_id: Annotated[UUID, Path(min_length=1, description="Run identifier")],
    service: RunsService = runs_service_dependency,
) -> RunOutputListing:
    try:
        files = await service.list_output_files(run_id=run_id)
    except (RunNotFoundError, RunOutputMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    entries: list[RunOutputFile] = []
    for relative_path, size in files:
        name = FilePath(relative_path).name
        content_type, _ = mimetypes.guess_type(name)
        normalized_path = FilePath(relative_path).as_posix()
        download_url = f"/api/v1/runs/{run_id}/outputs/{normalized_path}"
        entries.append(
            RunOutputFile(
                name=name,
                kind="normalized_workbook" if name.endswith((".xlsx", ".xlsm")) else None,
                content_type=content_type,
                byte_size=size,
                download_url=download_url,
            )
        )
    return RunOutputListing(files=entries)


@router.get(
    "/runs/{run_id}/outputs/{output_path:path}",
    response_class=FileResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Output not found"}},
)
async def download_run_output_endpoint(
    run_id: Annotated[UUID, Path(min_length=1, description="Run identifier")],
    output_path: str,
    service: RunsService = runs_service_dependency,
):
    try:
        path = await service.resolve_output_file(run_id=run_id, relative_path=output_path)
    except (RunNotFoundError, RunOutputMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(path=path, filename=path.name)
