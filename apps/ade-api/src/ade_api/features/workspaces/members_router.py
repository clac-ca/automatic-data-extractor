from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Response, Security, status
from fastapi import Path as PathParam

from ade_api.app.dependencies import get_workspaces_service
from ade_api.common.pagination import PageParams
from ade_api.core.http import require_authenticated, require_csrf, require_workspace
from ade_api.core.models import User

from .schemas import (
    WorkspaceMemberCreate,
    WorkspaceMemberOut,
    WorkspaceMemberPage,
    WorkspaceMemberUpdate,
)
from .service import WorkspacesService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/members",
    tags=["workspaces"],
    dependencies=[Security(require_authenticated)],
)
workspaces_service_dependency = Depends(get_workspaces_service)

WORKSPACE_MEMBER_CREATE_BODY = Body(...)
WORKSPACE_MEMBER_UPDATE_BODY = Body(...)


@router.get(
    "",
    response_model=WorkspaceMemberPage,
    response_model_exclude_none=True,
    summary="List workspace members with their roles",
)
async def list_workspace_members(
    workspace_id: Annotated[
        str,
        PathParam(
            min_length=1,
            description="Workspace identifier",
        ),
    ],
    page: Annotated[PageParams, Depends()],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.members.read"),
            scopes=["{workspace_id}"],
        ),
    ],
    user_id: Annotated[
        str | None,
        Query(
            description="Optional filter by user id",
        ),
    ] = None,
    include_inactive: Annotated[
        bool,
        Query(
            description="Include inactive users in the response.",
        ),
    ] = False,
    service: WorkspacesService = workspaces_service_dependency,
) -> WorkspaceMemberPage:
    return await service.list_workspace_members(
        workspace_id=workspace_id,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
        user_id=user_id,
        include_inactive=include_inactive,
    )


@router.post(
    "",
    dependencies=[Security(require_csrf)],
    response_model=WorkspaceMemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a workspace member with roles",
)
async def add_workspace_member(
    workspace_id: Annotated[
        str,
        PathParam(min_length=1, description="Workspace identifier"),
    ],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.members.manage"),
            scopes=["{workspace_id}"],
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
    "/{user_id}",
    dependencies=[Security(require_csrf)],
    response_model=WorkspaceMemberOut,
    summary="Replace workspace member roles",
)
async def update_workspace_member(
    workspace_id: Annotated[
        str,
        PathParam(min_length=1, description="Workspace identifier"),
    ],
    user_id: Annotated[
        str,
        PathParam(min_length=1, description="User identifier"),
    ],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.members.manage"),
            scopes=["{workspace_id}"],
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
    "/{user_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a workspace member",
)
async def remove_workspace_member(
    workspace_id: Annotated[
        str,
        PathParam(min_length=1, description="Workspace identifier"),
    ],
    user_id: Annotated[
        str,
        PathParam(min_length=1, description="User identifier"),
    ],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.members.manage"),
            scopes=["{workspace_id}"],
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
