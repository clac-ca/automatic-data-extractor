"""HTTP routes for build orchestration and streaming."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Security,
    status,
)
from fastapi import Path as PathParam
from sse_starlette.sse import EventSourceResponse

from ade_api.api.deps import SessionDep, get_builds_service, get_idempotency_service
from ade_api.common.sse import stream_ndjson_events
from ade_api.common.listing import (
    ListQueryParams,
    list_query_params,
    strict_list_query_guard,
)
from ade_api.common.sorting import resolve_sort
from ade_api.core.auth import AuthenticatedPrincipal
from ade_api.core.http import (
    get_current_principal,
    require_authenticated,
    require_csrf,
    require_workspace,
)
from ade_api.features.configs.exceptions import ConfigurationNotFoundError
from ade_api.features.idempotency import (
    IdempotencyService,
    build_request_hash,
    build_scope_key,
    require_idempotency_key,
)

from .exceptions import BuildNotFoundError
from .schemas import BuildCreateRequest, BuildPage, BuildResource
from .service import BuildsService
from .sorting import DEFAULT_SORT, ID_FIELD, SORT_FIELDS

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
        build = await service.prepare_build(
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


@router.get("/builds/{buildId}/events/stream")
async def stream_build_events_endpoint(
    build_id: BuildPath,
    request: Request,
    db_session: SessionDep,
    after_sequence: int | None = Query(default=None, ge=0),
    service: BuildsService = builds_service_dependency,
) -> EventSourceResponse:
    build = await service.get_build(build_id)
    if build is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Build not found")

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

    log_path = service.get_event_log_path(
        workspace_id=build.workspace_id,
        configuration_id=build.configuration_id,
        build_id=build.id,
    )
    await db_session.close()

    return EventSourceResponse(
        stream_ndjson_events(
            path=log_path,
            start_sequence=start_sequence,
            stop_events={"build.complete", "build.failed"},
            ping_interval=15,
        ),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
