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
from sse_starlette.sse import EventSourceResponse

from ade_api.api.deps import get_builds_service, get_idempotency_service
from ade_api.common.encoding import json_bytes
from ade_api.common.events import strip_sequence
from ade_api.common.listing import (
    ListQueryParams,
    list_query_params,
    strict_list_query_guard,
)
from ade_api.common.sorting import resolve_sort
from ade_api.common.sse import sse_json
from ade_api.core.auth import AuthenticatedPrincipal
from ade_api.core.http import get_current_principal, require_authenticated, require_csrf, require_workspace
from ade_api.features.idempotency import (
    IdempotencyService,
    build_request_hash,
    build_scope_key,
    require_idempotency_key,
)
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.models import BuildStatus

from .exceptions import BuildNotFoundError
from .schemas import BuildCreateRequest, BuildEventsPage, BuildPage, BuildResource
from .service import DEFAULT_EVENTS_PAGE_LIMIT, BuildsService
from .sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS
from .tasks import execute_build_background

router = APIRouter(tags=["builds"], dependencies=[Security(require_authenticated)])
builds_service_dependency = Depends(get_builds_service)

WorkspacePath = Annotated[
    UUID,
    PathParam(
        description="Workspace identifier",
        alias="workspaceId",
    ),
]
ConfigurationPath = Annotated[
    UUID,
    PathParam(
        description="Configuration identifier",
        alias="configurationId",
    ),
]
BuildPath = Annotated[
    UUID,
    PathParam(
        description="Build identifier",
        alias="buildId",
    ),
]


def _event_bytes(event: Any) -> bytes:
    return json_bytes(event) + b"\n"


@router.get(
    "/workspaces/{workspaceId}/configurations/{configurationId}/builds",
    response_model=BuildPage,
    response_model_exclude_none=True,
)
async def list_builds_endpoint(
    workspace_id: WorkspacePath,
    configuration_id: ConfigurationPath,
    list_query: Annotated[ListQueryParams, Depends(list_query_params)],
    _guard: Annotated[None, Depends(strict_list_query_guard())],
    _actor: Annotated[
        object,
        Security(
            require_workspace("workspace.configurations.read"),
            scopes=["{workspaceId}"],
        ),
    ],
    service: BuildsService = builds_service_dependency,
) -> BuildPage:
    try:
        order_by = resolve_sort(
            list_query.sort,
            allowed=SORT_FIELDS,
            default=DEFAULT_SORT,
            id_field=ID_FIELD,
        )
        return await service.list_builds(
            workspace_id=workspace_id,
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


@router.post(
    "/workspaces/{workspaceId}/configurations/{configurationId}/builds",
    response_model=BuildResource,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Security(require_csrf)],
)
async def create_build_endpoint(
    *,
    workspace_id: WorkspacePath,
    configuration_id: ConfigurationPath,
    payload: BuildCreateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    idempotency: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    _actor: Annotated[
        object,
        Security(
            require_workspace("workspace.configurations.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    service: BuildsService = builds_service_dependency,
) -> BuildResource:
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
        build, context = await service.prepare_build(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            options=payload.options,
            reason="manual",
        )
    except ConfigurationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    resource = service.to_resource(build)
    await idempotency.store_response(
        key=idempotency_key,
        scope_key=scope_key,
        request_hash=request_hash,
        status_code=status.HTTP_201_CREATED,
        body=resource,
    )
    background_tasks.add_task(
        execute_build_background,
        context.as_dict(),
        payload.options.model_dump(),
        service.settings.model_dump(mode="python"),
    )
    return resource


@router.get("/builds/{buildId}", response_model=BuildResource)
async def get_build_endpoint(
    build_id: BuildPath,
    service: BuildsService = builds_service_dependency,
) -> BuildResource:
    build = await service.get_build(build_id)
    if build is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Build not found")
    return service.to_resource(build)


@router.get(
    "/builds/{buildId}/events",
    response_model=BuildEventsPage,
    response_model_exclude_none=True,
)
async def list_build_events_endpoint(
    build_id: BuildPath,
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


@router.get("/builds/{buildId}/events/stream")
async def stream_build_events_endpoint(
    build_id: BuildPath,
    request: Request,
    after_sequence: int | None = Query(default=None, ge=0),
    service: BuildsService = builds_service_dependency,
) -> EventSourceResponse:
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

    async def event_stream() -> AsyncIterator[dict[str, str]]:
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

    return EventSourceResponse(
        event_stream(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
        ping=15,
    )
