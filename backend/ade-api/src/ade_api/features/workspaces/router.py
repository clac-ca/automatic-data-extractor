from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Response, Security, status

from ade_api.api.deps import get_workspaces_service, get_workspaces_service_read
from ade_api.common.cursor_listing import (
    CursorQueryParams,
    cursor_query_params,
    resolve_cursor_sort_sequence,
    strict_cursor_query_guard,
)
from ade_api.core.http import require_authenticated, require_csrf, require_global, require_workspace
from ade_db.models import User

from .deps import get_workspace_profile
from .schemas import (
    WorkspaceCreate,
    WorkspaceOut,
    WorkspacePage,
    WorkspaceUpdate,
)
from .service import WorkspacesService
from .sorting import DEFAULT_SORT, WORKSPACE_CURSOR_FIELDS

router = APIRouter(tags=["workspaces"], dependencies=[Security(require_authenticated)])
WorkspacesServiceDep = Annotated[WorkspacesService, Depends(get_workspaces_service)]
WorkspacesServiceReadDep = Annotated[
    WorkspacesService, Depends(get_workspaces_service_read)
]

WORKSPACE_CREATE_BODY = Body(...)
WORKSPACE_UPDATE_BODY = Body(...)

WorkspacePath = Annotated[
    UUID,
    Path(
        description="Workspace identifier",
        alias="workspaceId",
    ),
]


@router.post(
    "/workspaces",
    dependencies=[Security(require_csrf)],
    response_model=WorkspaceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspaces.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Administrator role required to create workspaces.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Specified owner could not be found or is inactive.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Workspace slug already exists.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Workspace name or slug is invalid.",
        },
    },
)
def create_workspace(
    admin_user: Annotated[
        User,
        Security(require_global("workspaces.create")),
    ],
    service: WorkspacesServiceDep,
    *,
    payload: WorkspaceCreate = WORKSPACE_CREATE_BODY,
) -> WorkspaceOut:
    workspace = service.create_workspace(
        user=admin_user,
        name=payload.name,
        slug=payload.slug,
        owner_user_id=payload.owner_user_id,
        settings=payload.settings,
        processing_paused=payload.processing_paused,
    )
    return workspace


@router.get(
    "/workspaces",
    response_model=WorkspacePage,
    status_code=status.HTTP_200_OK,
    summary="List workspaces for the authenticated user",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list workspaces.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Service account credentials cannot access workspace listings.",
        },
    },
)
def list_workspaces(
    current_user: Annotated[User, Security(require_authenticated)],
    list_query: Annotated[CursorQueryParams, Depends(cursor_query_params)],
    _guard: Annotated[None, Depends(strict_cursor_query_guard())],
    service: WorkspacesServiceReadDep,
) -> WorkspacePage:
    resolved_sort = resolve_cursor_sort_sequence(
        list_query.sort,
        cursor_fields=WORKSPACE_CURSOR_FIELDS,
        default=DEFAULT_SORT,
    )
    return service.list_workspaces(
        user=current_user,
        resolved_sort=resolved_sort,
        filters=list_query.filters,
        join_operator=list_query.join_operator,
        q=list_query.q,
        limit=list_query.limit,
        cursor=list_query.cursor,
        include_total=list_query.include_total,
    )


@router.get(
    "/workspaces/{workspaceId}",
    response_model=WorkspaceOut,
    status_code=status.HTTP_200_OK,
    summary="Retrieve workspace context by identifier",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to view workspace context.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace access denied for the authenticated user.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Workspace not found.",
        },
    },
)
def read_workspace(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.read"),
            scopes=["{workspaceId}"],
        ),
    ],
) -> WorkspaceOut:
    return workspace


@router.patch(
    "/workspaces/{workspaceId}",
    dependencies=[Security(require_csrf)],
    response_model=WorkspaceOut,
    status_code=status.HTTP_200_OK,
    summary="Update workspace metadata",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to update workspaces.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow settings management.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Workspace not found.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Workspace slug already exists.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Workspace name or slug is invalid.",
        },
    },
)
def update_workspace(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
    actor: Annotated[
        User,
        Security(
            require_workspace("workspace.settings.manage"),
            scopes=["{workspaceId}"],
        ),
    ],
    service: WorkspacesServiceDep,
    *,
    payload: WorkspaceUpdate = WORKSPACE_UPDATE_BODY,
) -> WorkspaceOut:
    workspace = service.update_workspace(
        user=actor,
        workspace_id=workspace.id,
        name=payload.name,
        slug=payload.slug,
        settings=payload.settings,
        processing_paused=payload.processing_paused,
    )
    return workspace


@router.delete(
    "/workspaces/{workspaceId}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a workspace",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to delete workspaces.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow workspace deletion.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Workspace not found.",
        },
    },
)
def delete_workspace(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.delete"),
            scopes=["{workspaceId}"],
        ),
    ],
    service: WorkspacesServiceDep,
) -> Response:
    service.delete_workspace(workspace_id=workspace.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/workspaces/{workspaceId}/default",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark a workspace as the caller's default",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to set the default workspace.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace access denied for the authenticated user.",
        },
    },
)
def set_default_workspace(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
    actor: Annotated[
        User,
        Security(
            require_workspace("workspace.read"),
            scopes=["{workspaceId}"],
        ),
    ],
    service: WorkspacesServiceDep,
) -> Response:
    service.set_default_workspace(
        workspace_id=workspace.id,
        user=actor,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
