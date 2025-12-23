"""HTTP routes for build orchestration and streaming."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Security,
    status,
)
from fastapi import Path as PathParam
from fastapi.responses import StreamingResponse

from ade_api.api.deps import get_builds_service
from ade_api.common.encoding import json_bytes
from ade_api.common.events import strip_sequence
from ade_api.common.sse import sse_json
from ade_api.core.http import require_authenticated, require_csrf, require_workspace
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.models import BuildStatus
from ade_api.settings import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

from .exceptions import BuildNotFoundError
from .schemas import (
    BuildCreateRequest,
    BuildEventsPage,
    BuildFilters,
    BuildListParams,
    BuildPage,
    BuildResource,
)
from .service import DEFAULT_EVENTS_PAGE_LIMIT, BuildsService
from .tasks import execute_build_background

router = APIRouter(tags=["builds"], dependencies=[Security(require_authenticated)])
builds_service_dependency = Depends(get_builds_service)


async def resolve_build_list_params(
    page: Annotated[int, Query(ge=1, description="1-based page number")] = 1,
    page_size: Annotated[int | None, Query(ge=1, le=MAX_PAGE_SIZE, alias="page_size")] = None,
    limit: Annotated[int | None, Query(ge=1, le=MAX_PAGE_SIZE)] = None,
    include_total: Annotated[bool, Query(description="Include total item count")] = False,
) -> BuildListParams:
    page_size_value = limit if limit is not None else page_size or DEFAULT_PAGE_SIZE
    return BuildListParams(page=page, page_size=page_size_value, include_total=include_total)


async def resolve_build_filters(
    status: Annotated[list[BuildStatus] | None, Query()] = None,
) -> BuildFilters:
    return BuildFilters(status=status)


def _event_bytes(event: Any) -> bytes:
    return json_bytes(event) + b"\n"


@router.get(
    "/workspaces/{workspace_id}/configurations/{configuration_id}/builds",
    response_model=BuildPage,
    response_model_exclude_none=True,
)
async def list_builds_endpoint(
    workspace_id: Annotated[
        UUID,
        PathParam(description="Workspace identifier"),
    ],
    configuration_id: Annotated[
        UUID,
        PathParam(description="Configuration identifier"),
    ],
    page: Annotated[BuildListParams, Depends(resolve_build_list_params)],
    filters: Annotated[BuildFilters, Depends(resolve_build_filters)],
    _actor: Annotated[
        object,
        Security(
            require_workspace("workspace.configurations.read"),
            scopes=["{workspace_id}"],
        ),
    ],
    service: BuildsService = builds_service_dependency,
) -> BuildPage:
    statuses = [BuildStatus(status) for status in filters.status] if filters.status else None
    try:
        return await service.list_builds(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            statuses=statuses,
            page=page.page,
            page_size=page.page_size,
            include_total=page.include_total,
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/workspaces/{workspace_id}/configurations/{configuration_id}/builds",
    response_model=BuildResource,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
async def create_build_endpoint(
    *,
    workspace_id: Annotated[
        UUID,
        PathParam(description="Workspace identifier"),
    ],
    configuration_id: Annotated[
        UUID,
        PathParam(description="Configuration identifier"),
    ],
    payload: BuildCreateRequest,
    background_tasks: BackgroundTasks,
    _actor: Annotated[
        object,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspace_id}"],
        ),
    ],
    service: BuildsService = builds_service_dependency,
) -> BuildResource:
    try:
        build, context = await service.prepare_build(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            options=payload.options,
            reason="manual",
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    resource = service.to_resource(build)
    background_tasks.add_task(
        execute_build_background,
        context.as_dict(),
        payload.options.model_dump(),
        service.settings.model_dump(mode="python"),
    )
    return resource


@router.get("/builds/{build_id}", response_model=BuildResource)
async def get_build_endpoint(
    build_id: Annotated[UUID, PathParam(description="Build identifier")],
    service: BuildsService = builds_service_dependency,
) -> BuildResource:
    build = await service.get_build(build_id)
    if build is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Build not found")
    return service.to_resource(build)


@router.get(
    "/builds/{build_id}/events",
    response_model=BuildEventsPage,
    response_model_exclude_none=True,
)
async def list_build_events_endpoint(
    build_id: Annotated[UUID, PathParam(description="Build identifier")],
    format: Literal["json", "ndjson"] = Query(default="json"),
    after_sequence: int | None = Query(default=None, ge=0),
    limit: int = Query(default=DEFAULT_EVENTS_PAGE_LIMIT, ge=1, le=DEFAULT_EVENTS_PAGE_LIMIT),
    service: BuildsService = builds_service_dependency,
) -> BuildEventsPage | StreamingResponse:
    try:
        events, next_after_sequence = await service.get_build_events(
            build_id=build_id,
            after_sequence=after_sequence,
            limit=limit,
        )
    except BuildNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if format == "ndjson":

        async def event_stream() -> AsyncIterator[bytes]:
            for event in events:
                yield _event_bytes(event)

        return StreamingResponse(event_stream(), media_type="application/x-ndjson")

    return BuildEventsPage(items=events, next_after_sequence=next_after_sequence)


@router.get("/builds/{build_id}/events/stream")
async def stream_build_events_endpoint(
    build_id: Annotated[UUID, PathParam(description="Build identifier")],
    request: Request,
    after_sequence: int | None = Query(default=None, ge=0),
    service: BuildsService = builds_service_dependency,
) -> StreamingResponse:
    build = await service.get_build(build_id)
    if build is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Build not found")

    # Kick off execution if this build is still pending; stream will then tail events.
    await service.launch_build_if_needed(build=build, reason="sse_stream", run_id=None)

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

        async with service.subscribe_to_events(build) as subscription:
            for event in service.iter_events(build=build, after_sequence=start_sequence):
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
                if event.get("event") in {"build.complete", "build.failed"}:
                    return

            build_already_finished = build.status in {
                BuildStatus.READY,
                BuildStatus.FAILED,
                BuildStatus.CANCELLED,
            }
            if build_already_finished:
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
                if live_event.get("event") in {"build.complete", "build.failed"}:
                    break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
