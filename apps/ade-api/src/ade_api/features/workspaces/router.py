from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Response, Security, status

from ade_api.app.dependencies import get_workspace_profile, get_workspaces_service
from ade_api.common.pagination import PageParams
from ade_api.core.http import require_authenticated, require_csrf, require_global, require_workspace
from ade_api.core.models import User

from .schemas import (
    WorkspaceCreate,
    WorkspaceOut,
    WorkspacePage,
    WorkspaceUpdate,
)
from .service import WorkspacesService

router = APIRouter(tags=["workspaces"], dependencies=[Security(require_authenticated)])
workspaces_service_dependency = Depends(get_workspaces_service)

WORKSPACE_CREATE_BODY = Body(...)
WORKSPACE_UPDATE_BODY = Body(...)


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
async def create_workspace(
    admin_user: Annotated[
        User,
        Security(require_global("workspaces.create")),
    ],
    service: WorkspacesService = workspaces_service_dependency,
    *,
    payload: WorkspaceCreate = WORKSPACE_CREATE_BODY,
) -> WorkspaceOut:
    workspace = await service.create_workspace(
        user=admin_user,
        name=payload.name,
        slug=payload.slug,
        owner_user_id=payload.owner_user_id,
        settings=payload.settings,
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
async def list_workspaces(
    current_user: Annotated[User, Security(require_authenticated)],
    page: Annotated[PageParams, Depends()],
    service: WorkspacesService = workspaces_service_dependency,
) -> WorkspacePage:
    page_result = await service.list_workspaces(
        user=current_user,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    return WorkspacePage(**page_result.model_dump())


@router.get(
    "/workspaces/{workspace_id}",
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
async def read_workspace(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> WorkspaceOut:
    return workspace


@router.patch(
    "/workspaces/{workspace_id}",
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
async def update_workspace(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
    actor: Annotated[
        User,
        Security(
            require_workspace("workspace.settings.manage"),
            scopes=["{workspace_id}"],
        ),
    ],
    service: WorkspacesService = workspaces_service_dependency,
    *,
    payload: WorkspaceUpdate = WORKSPACE_UPDATE_BODY,
) -> WorkspaceOut:
    workspace = await service.update_workspace(
        user=actor,
        workspace_id=workspace.id,
        name=payload.name,
        slug=payload.slug,
        settings=payload.settings,
    )
    return workspace


@router.delete(
    "/workspaces/{workspace_id}",
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
async def delete_workspace(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("workspace.delete"),
            scopes=["{workspace_id}"],
        ),
    ],
    service: WorkspacesService = workspaces_service_dependency,
) -> Response:
    await service.delete_workspace(workspace_id=workspace.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/workspaces/{workspace_id}/default",
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
async def set_default_workspace(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
    actor: Annotated[
        User,
        Security(
            require_workspace("workspace.read"),
            scopes=["{workspace_id}"],
        ),
    ],
    service: WorkspacesService = workspaces_service_dependency,
) -> Response:
    await service.set_default_workspace(
        workspace_id=workspace.id,
        user=actor,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
