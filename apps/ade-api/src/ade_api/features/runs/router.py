"""FastAPI router exposing ADE run APIs."""

from __future__ import annotations

import logging
import mimetypes
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal
from uuid import UUID

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

from ade_api.api.deps import (
    get_runs_service,
)
from ade_api.common.downloads import build_content_disposition
from ade_api.common.encoding import json_bytes
from ade_api.common.events import EventRecord, strip_sequence
from ade_api.common.ids import UUIDStr
from ade_api.common.logging import log_context
from ade_api.common.pagination import PageParams
from ade_api.common.sse import sse_json
from ade_api.core.http import require_authenticated, require_csrf
from ade_api.db.session import get_sessionmaker
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.models import RunStatus
from ade_api.settings import Settings

from .event_stream import get_run_event_streams
from .exceptions import (
    RunDocumentMissingError,
    RunInputMissingError,
    RunLogsFileMissingError,
    RunNotFoundError,
    RunOutputMissingError,
    RunOutputNotReadyError,
)
from .schemas import (
    RunCreateOptions,
    RunCreateRequest,
    RunEventsPage,
    RunFilters,
    RunInput,
    RunOutput,
    RunPage,
    RunResource,
)
from .service import (
    DEFAULT_EVENTS_PAGE_LIMIT,
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


def _event_bytes(event: EventRecord) -> bytes:
    return json_bytes(event) + b"\n"


async def _execute_run_background(
    run_id: str,
    options_data: dict[str, Any],
    settings_payload: dict[str, Any],
) -> None:
    """Run execution coroutine used for non-streaming requests."""

    settings = Settings(**settings_payload)
    session_factory = get_sessionmaker(settings=settings)
    options = RunCreateOptions(**options_data)
    event_streams = get_run_event_streams()
    async with session_factory() as session:
        service = RunsService(
            session=session,
            settings=settings,
            event_streams=event_streams,
            build_event_streams=event_streams,
        )
        try:
            await service.run_to_completion(run_id=UUID(run_id), options=options)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception(
                "run.background.failed",
                extra=log_context(run_id=run_id),
            )
            async for event in service.handle_background_failure(
                run_id=UUID(run_id),
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
    configuration_id: Annotated[UUID, Path(description="Configuration identifier")],
    payload: RunCreateRequest,
    background_tasks: BackgroundTasks,
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

    resource = await service.to_resource(run)
    options_dict = payload.options.model_dump()
    background_tasks.add_task(
        _execute_run_background,
        str(run.id),
        options_dict,
        service.settings.model_dump(mode="python"),
    )
    return resource


@router.get(
    "/configurations/{configuration_id}/runs",
    response_model=RunPage,
    response_model_exclude_none=True,
)
async def list_configuration_runs_endpoint(
    configuration_id: Annotated[UUID, Path(description="Configuration identifier")],
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
    workspace_id: Annotated[UUID, Path(description="Workspace identifier")],
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
    run_id: Annotated[UUID, Path(description="Run identifier")],
    service: RunsService = runs_service_dependency,
) -> RunResource:
    run = await service.get_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run not found")
    return await service.to_resource(run)


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
