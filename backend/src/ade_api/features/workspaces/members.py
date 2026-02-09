from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Response, Security, status
from fastapi import Path as PathParam

from ade_api.api.deps import get_workspaces_service
from ade_api.common.cursor_listing import (
    CursorQueryParams,
    cursor_query_params,
    resolve_cursor_sort_sequence,
    strict_cursor_query_guard,
)
from ade_api.core.http import require_authenticated, require_csrf, require_workspace
from ade_db.models import User

from .schemas import (
    WorkspaceMemberCreate,
    WorkspaceMemberOut,
    WorkspaceMemberPage,
    WorkspaceMemberUpdate,
)
from .service import WorkspacesService
from .sorting import MEMBER_CURSOR_FIELDS, MEMBER_DEFAULT_SORT

router = APIRouter(
    prefix="/workspaces/{workspaceId}/members",
    tags=["workspaces"],
    dependencies=[Security(require_authenticated)],
)
workspaces_service_dependency = Depends(get_workspaces_service)

WORKSPACE_MEMBER_CREATE_BODY = Body(...)
WORKSPACE_MEMBER_UPDATE_BODY = Body(...)

WorkspacePath = Annotated[
    UUID,
    Path(
        description="Workspace identifier",
        alias="workspaceId",
    ),
]
UserPath = Annotated[
    UUID,
    PathParam(description="User identifier", alias="userId"),
]


@router.get(
    "",
    response_model=WorkspaceMemberPage,
    response_model_exclude_none=True,
    summary="List workspace members with their roles",
)
def list_workspace_members(
    workspace_id: WorkspacePath,
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[None, Depends(strict_cursor_query_guard())],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.members.read"),
            scopes=["{workspaceId}"],
        ),
    ],
    service: WorkspacesService = workspaces_service_dependency,
) -> WorkspaceMemberPage:
    resolved_sort = resolve_cursor_sort_sequence(
        list_query.sort,
        cursor_fields=MEMBER_CURSOR_FIELDS,
        default=MEMBER_DEFAULT_SORT,
    )
    return service.list_workspace_members(
        workspace_id=workspace_id,
        resolved_sort=resolved_sort,
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        limit=list_query.limit,
        cursor=list_query.cursor,
        include_total=list_query.include_total,
    )


@router.post(
    "",
    dependencies=[Security(require_csrf)],
    response_model=WorkspaceMemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a workspace member with roles",
)
def add_workspace_member(
    workspace_id: WorkspacePath,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.members.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    service: WorkspacesService = workspaces_service_dependency,
    *,
    payload: WorkspaceMemberCreate = WORKSPACE_MEMBER_CREATE_BODY,
) -> WorkspaceMemberOut:
    return service.add_workspace_member(
        workspace_id=workspace_id,
        payload=payload,
    )


@router.put(
    "/{userId}",
    dependencies=[Security(require_csrf)],
    response_model=WorkspaceMemberOut,
    summary="Replace workspace member roles",
)
def update_workspace_member(
    workspace_id: WorkspacePath,
    user_id: UserPath,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.members.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    service: WorkspacesService = workspaces_service_dependency,
    *,
    payload: WorkspaceMemberUpdate = WORKSPACE_MEMBER_UPDATE_BODY,
) -> WorkspaceMemberOut:
    return service.update_workspace_member_roles(
        workspace_id=workspace_id,
        user_id=user_id,
        payload=payload,
    )


@router.delete(
    "/{userId}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a workspace member",
)
def remove_workspace_member(
    workspace_id: WorkspacePath,
    user_id: UserPath,
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.members.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    service: WorkspacesService = workspaces_service_dependency,
) -> Response:
    service.remove_workspace_member(
        workspace_id=workspace_id,
        user_id=user_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
