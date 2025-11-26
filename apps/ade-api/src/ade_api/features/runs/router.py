"""FastAPI router exposing ADE run APIs."""

from __future__ import annotations

import logging
import mimetypes
from collections.abc import AsyncIterator
from pathlib import Path as FilePath
from typing import Annotated, Any, Literal

from ade_engine.schemas import AdeEvent, RunSummaryV1
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Path,
    Query,
    Security,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse

from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.settings import Settings
from ade_api.shared.db.session import get_sessionmaker
from ade_api.shared.dependency import (
    get_runs_service,
    require_authenticated,
    require_csrf,
)
from ade_api.shared.pagination import PageParams

from .models import RunStatus
from .schemas import (
    RunCreateOptions,
    RunCreateRequest,
    RunDiagnosticsV1,
    RunEventsPage,
    RunFilters,
    RunLogsResponse,
    RunOutputFile,
    RunOutputListing,
    RunPage,
    RunResource,
)
from .service import (
    DEFAULT_STREAM_LIMIT,
    RunDocumentMissingError,
    RunEnvironmentNotReadyError,
    RunExecutionContext,
    RunInputMissingError,
    RunLogsFileMissingError,
    RunNotFoundError,
    RunOutputMissingError,
    RunsService,
    RunStreamFrame,
)

router = APIRouter(
    tags=["runs"],
    dependencies=[Security(require_authenticated)],
)
runs_service_dependency = Depends(get_runs_service)
logger = logging.getLogger(__name__)


def _event_bytes(event: RunStreamFrame) -> bytes:
    return event.model_dump_json().encode("utf-8") + b"\n"


async def _execute_run_background(
    context_data: dict[str, str],
    options_data: dict[str, Any],
    settings: Settings,
) -> None:
    """Run execution coroutine used for non-streaming requests."""

    session_factory = get_sessionmaker(settings=settings)
    context = RunExecutionContext.from_dict(context_data)
    options = RunCreateOptions(**options_data)
    async with session_factory() as session:
        service = RunsService(session=session, settings=settings)
        try:
            await service.run_to_completion(context=context, options=options)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Background ADE run failed", extra={"run_id": context.run_id})


@router.post(
    "/configurations/{configuration_id}/runs",
    response_model=RunResource,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
async def create_run_endpoint(
    *,
    configuration_id: Annotated[str, Path(min_length=1, description="Configuration identifier")],
    payload: RunCreateRequest,
    background_tasks: BackgroundTasks,
    service: RunsService = runs_service_dependency,
) -> RunResource | StreamingResponse:
    """Create a run for ``configuration_id`` and optionally stream execution events."""

    try:
        run, context = await service.prepare_run(
            configuration_id=configuration_id, options=payload.options
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunDocumentMissingError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RunInputMissingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RunEnvironmentNotReadyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    resource = service.to_resource(run)
    if not payload.stream:
        context_dict = context.as_dict()
        options_dict = payload.options.model_dump()
        background_tasks.add_task(
            _execute_run_background,
            context_dict,
            options_dict,
            service.settings,
        )
        return resource

    async def event_stream() -> AsyncIterator[bytes]:
        try:
            async for event in service.stream_run(context=context, options=payload.options):
                yield _event_bytes(event)
        except RunNotFoundError:
            logger.warning("Run disappeared during streaming", extra={"run_id": context.run_id})
            return

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.get(
    "/workspaces/{workspace_id}/runs",
    response_model=RunPage,
    response_model_exclude_none=True,
)
async def list_workspace_runs_endpoint(
    workspace_id: Annotated[str, Path(min_length=1, description="Workspace identifier")],
    page: Annotated[PageParams, Depends()],
    filters: Annotated[RunFilters, Depends()],
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
    run_id: Annotated[str, Path(min_length=1, description="Run identifier")],
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
    run_id: Annotated[str, Path(min_length=1, description="Run identifier")],
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
    run_id: Annotated[str, Path(min_length=1, description="Run identifier")],
    format: Literal["json", "ndjson"] = Query(default="json"),
    cursor: str | None = Query(default=None, description="Opaque cursor from previous page"),
    limit: int = Query(default=DEFAULT_STREAM_LIMIT, ge=1, le=DEFAULT_STREAM_LIMIT),
    service: RunsService = runs_service_dependency,
) -> RunEventsPage | StreamingResponse:
    try:
        cursor_value = int(cursor) if cursor is not None else None
    except ValueError as exc:  # pragma: no cover - defensive
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid cursor") from exc

    try:
        events, next_cursor = await service.get_run_events(
            run_id=run_id,
            cursor=cursor_value,
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
        next_cursor=str(next_cursor) if next_cursor is not None else None,
    )


@router.get("/runs/{run_id}/logs", response_model=RunLogsResponse)
async def get_run_logs_endpoint(
    run_id: Annotated[str, Path(min_length=1, description="Run identifier")],
    after_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=DEFAULT_STREAM_LIMIT, ge=1, le=DEFAULT_STREAM_LIMIT),
    service: RunsService = runs_service_dependency,
) -> RunLogsResponse:
    run = await service.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run not found")
    return await service.get_logs(run_id=run_id, after_id=after_id, limit=limit)


@router.get(
    "/runs/{run_id}/logfile",
    response_class=FileResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Logs unavailable"}},
)
async def download_run_logs_file_endpoint(
    run_id: Annotated[str, Path(min_length=1, description="Run identifier")],
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
    run_id: Annotated[str, Path(min_length=1, description="Run identifier")],
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
    "/runs/{run_id}/diagnostics",
    response_model=RunDiagnosticsV1,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Diagnostics not available"}},
)
async def get_run_diagnostics_endpoint(
    run_id: Annotated[str, Path(min_length=1, description="Run identifier")],
    service: RunsService = runs_service_dependency,
) -> RunDiagnosticsV1:
    try:
        return await service.get_run_diagnostics(run_id=run_id)
    except (RunNotFoundError, RunOutputMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/runs/{run_id}/outputs/{output_path:path}",
    response_class=FileResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Output not found"}},
)
async def download_run_output_endpoint(
    run_id: Annotated[str, Path(min_length=1, description="Run identifier")],
    output_path: str,
    service: RunsService = runs_service_dependency,
):
    try:
        path = await service.resolve_output_file(run_id=run_id, relative_path=output_path)
    except (RunNotFoundError, RunOutputMissingError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(path=path, filename=path.name)
