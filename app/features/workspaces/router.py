from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, status

from app.core.responses import DefaultResponse
from app.core.schema import ErrorMessage

from ..auth.dependencies import bind_current_user
from ..auth.security import access_control
from ..users.models import User
from .dependencies import get_workspaces_service, require_workspace_context
from .schemas import (
    WorkspaceContext,
    WorkspaceCreate,
    WorkspaceDefaultSelection,
    WorkspaceMember,
    WorkspaceMemberCreate,
    WorkspaceMemberUpdate,
    WorkspaceProfile,
    WorkspaceUpdate,
)
from .service import WorkspacesService

router = APIRouter(tags=["workspaces"])

WORKSPACE_MEMBER_BODY = Body(...)
WORKSPACE_CREATE_BODY = Body(...)
WORKSPACE_UPDATE_BODY = Body(...)
WORKSPACE_MEMBER_UPDATE_BODY = Body(...)

UserDep = Annotated[User, Depends(bind_current_user)]
WorkspaceContextDep = Annotated[WorkspaceContext, Depends(require_workspace_context)]
WorkspaceServiceDep = Annotated[WorkspacesService, Depends(get_workspaces_service)]
AdminWorkspaceServiceDep = Annotated[
    WorkspacesService,
    Depends(access_control(require_admin=True, service_dependency=get_workspaces_service)),
]
WorkspaceMembersReadServiceDep = Annotated[
    WorkspacesService,
    Depends(
        access_control(
            permissions={"workspace:members:read"},
            require_workspace=True,
            service_dependency=get_workspaces_service,
        )
    ),
]
WorkspaceMembersManageServiceDep = Annotated[
    WorkspacesService,
    Depends(
        access_control(
            permissions={"workspace:members:manage"},
            require_workspace=True,
            service_dependency=get_workspaces_service,
        )
    ),
]
WorkspaceSettingsServiceDep = Annotated[
    WorkspacesService,
    Depends(
        access_control(
            permissions={"workspace:settings:manage"},
            require_workspace=True,
            service_dependency=get_workspaces_service,
        )
    ),
]
WorkspaceScopedServiceDep = Annotated[
    WorkspacesService,
    Depends(
        access_control(
            require_workspace=True,
            service_dependency=get_workspaces_service,
        )
    ),
]


@router.post(
    "/workspaces",
    response_model=WorkspaceProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspaces.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Administrator role required to create workspaces.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Specified owner could not be found or is inactive.",
            "model": ErrorMessage,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Workspace slug already exists.",
            "model": ErrorMessage,
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Workspace name or slug is invalid.",
            "model": ErrorMessage,
        },
    },
)
async def create_workspace(
    current_user: UserDep,
    service: AdminWorkspaceServiceDep,
    *,
    payload: WorkspaceCreate = WORKSPACE_CREATE_BODY,
) -> WorkspaceProfile:
    workspace = await service.create_workspace(
        user=current_user,
        name=payload.name,
        slug=payload.slug,
        owner_user_id=payload.owner_user_id,
        settings=payload.settings,
    )
    return workspace


@router.get(
    "/workspaces",
    response_model=list[WorkspaceProfile],
    status_code=status.HTTP_200_OK,
    summary="List workspaces for the authenticated user",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list workspaces.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Service account credentials cannot access workspace listings.",
            "model": ErrorMessage,
        },
    },
)
async def list_workspaces(
    current_user: UserDep,
    service: WorkspaceServiceDep,
) -> list[WorkspaceProfile]:
    memberships = await service.list_memberships(user=current_user)
    return memberships


@router.get(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceContext,
    status_code=status.HTTP_200_OK,
    summary="Retrieve workspace context by identifier",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to view workspace context.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace access denied for the authenticated user.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Workspace not found.",
            "model": ErrorMessage,
        },
    },
)
async def read_workspace(selection: WorkspaceContextDep) -> WorkspaceContext:
    return selection


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=list[WorkspaceMember],
    status_code=status.HTTP_200_OK,
    summary="List members within the workspace",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list workspace members.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow member access.",
            "model": ErrorMessage,
        },
    },
)
async def list_members(
    _: WorkspaceContextDep,
    service: WorkspaceMembersReadServiceDep,
) -> list[WorkspaceMember]:
    memberships = await service.list_members()
    return memberships


@router.post(
    "/workspaces/{workspace_id}/members",
    response_model=WorkspaceMember,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member to a workspace",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace members.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow member management.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Workspace or user not found.",
            "model": ErrorMessage,
        },
        status.HTTP_409_CONFLICT: {
            "description": "User is already a member of the workspace.",
            "model": ErrorMessage,
        },
    },
)
async def add_member(
    _: WorkspaceContextDep,
    service: WorkspaceMembersManageServiceDep,
    *,
    payload: WorkspaceMemberCreate = WORKSPACE_MEMBER_BODY,
) -> WorkspaceMember:
    membership = await service.add_member(
        user_id=payload.user_id,
        role=payload.role,
    )
    return membership


@router.patch(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceProfile,
    status_code=status.HTTP_200_OK,
    summary="Update workspace metadata",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to update workspaces.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow settings management.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Workspace not found.",
            "model": ErrorMessage,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Workspace slug already exists.",
            "model": ErrorMessage,
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Workspace name or slug is invalid.",
            "model": ErrorMessage,
        },
    },
)
async def update_workspace(
    current_user: UserDep,
    _: WorkspaceContextDep,
    service: WorkspaceSettingsServiceDep,
    *,
    payload: WorkspaceUpdate = WORKSPACE_UPDATE_BODY,
) -> WorkspaceProfile:
    workspace = await service.update_workspace(
        user=current_user,
        name=payload.name,
        slug=payload.slug,
        settings=payload.settings,
    )
    return workspace


@router.delete(
    "/workspaces/{workspace_id}",
    response_model=DefaultResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a workspace",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to delete workspaces.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow workspace deletion.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Workspace not found.",
            "model": ErrorMessage,
        },
    },
)
async def delete_workspace(
    _: WorkspaceContextDep,
    service: WorkspaceSettingsServiceDep,
) -> DefaultResponse:
    await service.delete_workspace()
    return DefaultResponse.success("Workspace deleted")


@router.patch(
    "/workspaces/{workspace_id}/members/{membership_id}",
    response_model=WorkspaceMember,
    status_code=status.HTTP_200_OK,
    summary="Update a workspace member",
    response_model_exclude_none=True,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Workspace must retain at least one owner.",
            "model": ErrorMessage,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace members.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow member management.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Membership not found within the workspace.",
            "model": ErrorMessage,
        },
    },
)
async def update_member(
    _: WorkspaceContextDep,
    service: WorkspaceMembersManageServiceDep,
    membership_id: str = Path(..., min_length=1, description="Membership identifier"),
    *,
    payload: WorkspaceMemberUpdate = WORKSPACE_MEMBER_UPDATE_BODY,
) -> WorkspaceMember:
    membership = await service.update_member_role(
        membership_id=membership_id,
        role=payload.role,
    )
    return membership


@router.delete(
    "/workspaces/{workspace_id}/members/{membership_id}",
    response_model=DefaultResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove a workspace member",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Workspace must retain at least one owner.",
            "model": ErrorMessage,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace members.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow member management.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Membership not found within the workspace.",
            "model": ErrorMessage,
        },
    },
)
async def remove_member(
    _: WorkspaceContextDep,
    service: WorkspaceMembersManageServiceDep,
    membership_id: str = Path(..., min_length=1, description="Membership identifier"),
) -> DefaultResponse:
    await service.remove_member(membership_id=membership_id)
    return DefaultResponse.success("Workspace member removed")


@router.post(
    "/workspaces/{workspace_id}/default",
    response_model=WorkspaceDefaultSelection,
    status_code=status.HTTP_200_OK,
    summary="Mark a workspace as the caller's default",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to set the default workspace.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace access denied for the authenticated user.",
            "model": ErrorMessage,
        },
    },
)
async def set_default_workspace(
    current_user: UserDep,
    _: WorkspaceContextDep,
    service: WorkspaceScopedServiceDep,
) -> WorkspaceDefaultSelection:
    selection = await service.set_default_workspace(user=current_user)
    return selection


__all__ = ["router"]
