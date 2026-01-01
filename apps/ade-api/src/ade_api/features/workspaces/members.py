from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Response, Security, status
from fastapi import Path as PathParam

from ade_api.api.deps import get_workspaces_service
from ade_api.common.listing import ListQueryParams, list_query_params, strict_list_query_guard
from ade_api.core.http import require_authenticated, require_csrf, require_workspace
from ade_api.models import User

from .schemas import (
    WorkspaceMemberCreate,
    WorkspaceMemberOut,
    WorkspaceMemberPage,
    WorkspaceMemberUpdate,
)
from .service import WorkspacesService

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
async def list_workspace_members(
    workspace_id: WorkspacePath,
    list_query: Annotated[ListQueryParams, Depends(list_query_params)],
    _guard: Annotated[None, Depends(strict_list_query_guard())],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.members.read"),
            scopes=["{workspaceId}"],
        ),
    ],
    service: WorkspacesService = workspaces_service_dependency,
) -> WorkspaceMemberPage:
    return await service.list_workspace_members(
        workspace_id=workspace_id,
        sort=list_query.sort,
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        page=list_query.page,
        per_page=list_query.per_page,
    )


@router.post(
    "",
    dependencies=[Security(require_csrf)],
    response_model=WorkspaceMemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a workspace member with roles",
)
async def add_workspace_member(
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
    return await service.add_workspace_member(
        workspace_id=workspace_id,
        payload=payload,
    )


@router.put(
    "/{userId}",
    dependencies=[Security(require_csrf)],
    response_model=WorkspaceMemberOut,
    summary="Replace workspace member roles",
)
async def update_workspace_member(
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
    return await service.update_workspace_member_roles(
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
async def remove_workspace_member(
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
    await service.remove_workspace_member(
        workspace_id=workspace_id,
        user_id=user_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
