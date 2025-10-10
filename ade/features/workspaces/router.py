from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from ade.api.security import require_authenticated, require_csrf, require_global, require_workspace
from ade.core.responses import DefaultResponse
from ade.core.schema import ErrorMessage
from ade.db.session import get_session

from ..roles.models import Role
from ..roles.schemas import RoleCreate, RoleRead, RoleUpdate
from ..users.models import User
from .dependencies import get_workspace_profile
from .schemas import (
    WorkspaceCreate,
    WorkspaceDefaultSelection,
    WorkspaceMember,
    WorkspaceMemberCreate,
    WorkspaceMemberRolesUpdate,
    WorkspaceProfile,
    WorkspaceUpdate,
)
from .service import WorkspacesService

router = APIRouter(tags=["workspaces"], dependencies=[Security(require_authenticated)])

WORKSPACE_MEMBER_BODY = Body(...)
WORKSPACE_CREATE_BODY = Body(...)
WORKSPACE_UPDATE_BODY = Body(...)
WORKSPACE_MEMBER_UPDATE_BODY = Body(...)


def _serialize_role(role: Role) -> RoleRead:
    return RoleRead(
        role_id=role.id,
        slug=role.slug,
        name=role.name,
        description=role.description,
        scope_type=role.scope_type,
        scope_id=role.scope_id,
        permissions=[permission.permission_key for permission in role.permissions],
        built_in=role.built_in,
        editable=role.editable,
    )

@router.post(
    "/workspaces",
    dependencies=[Security(require_csrf)],
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
    admin_user: Annotated[
        User,
        Security(require_global("Workspaces.Create")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    *,
    payload: WorkspaceCreate = WORKSPACE_CREATE_BODY,
) -> WorkspaceProfile:
    service = WorkspacesService(session=session)
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
    current_user: Annotated[User, Security(require_authenticated)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[WorkspaceProfile]:
    service = WorkspacesService(session=session)
    memberships = await service.list_memberships(user=current_user)
    return memberships


@router.get(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceProfile,
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
async def read_workspace(
    workspace: Annotated[WorkspaceProfile, Depends(get_workspace_profile)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> WorkspaceProfile:
    return workspace


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
    workspace: Annotated[WorkspaceProfile, Depends(get_workspace_profile)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Members.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[WorkspaceMember]:
    service = WorkspacesService(session=session)
    memberships = await service.list_members(
        workspace_id=workspace.workspace_id
    )
    return memberships


@router.get(
    "/workspaces/{workspace_id}/roles",
    response_model=list[RoleRead],
    status_code=status.HTTP_200_OK,
    summary="List roles available to the workspace",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list workspace roles.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow viewing role definitions.",
            "model": ErrorMessage,
        },
    },
)
async def list_workspace_roles(
    workspace: Annotated[WorkspaceProfile, Depends(get_workspace_profile)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Roles.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[RoleRead]:
    service = WorkspacesService(session=session)
    roles = await service.list_workspace_roles(workspace.workspace_id)
    return [_serialize_role(role) for role in roles]


@router.post(
    "/workspaces/{workspace_id}/roles",
    dependencies=[Security(require_csrf)],
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace role",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "System roles cannot be managed via this endpoint.",
            "model": ErrorMessage,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace roles.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow managing roles.",
            "model": ErrorMessage,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Role slug already exists or conflicts with a system role.",
            "model": ErrorMessage,
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Invalid role name, slug, or permissions.",
            "model": ErrorMessage,
        },
    },
)
async def create_workspace_role(
    workspace: Annotated[WorkspaceProfile, Depends(get_workspace_profile)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Roles.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: RoleCreate,
) -> RoleRead:
    service = WorkspacesService(session=session)
    role = await service.create_workspace_role(
        workspace_id=workspace.workspace_id,
        payload=payload,
        actor=actor,
    )
    return _serialize_role(role)


@router.put(
    "/workspaces/{workspace_id}/roles/{role_id}",
    dependencies=[Security(require_csrf)],
    response_model=RoleRead,
    status_code=status.HTTP_200_OK,
    summary="Update a workspace role",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "System roles cannot be modified.",
            "model": ErrorMessage,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace roles.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow managing roles.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Role not found for this workspace.",
            "model": ErrorMessage,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Operation would violate governor guardrails.",
            "model": ErrorMessage,
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Invalid role payload.",
            "model": ErrorMessage,
        },
    },
)
async def update_workspace_role(
    workspace: Annotated[WorkspaceProfile, Depends(get_workspace_profile)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Roles.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    role_id: Annotated[str, Path(min_length=1)],
    payload: RoleUpdate,
) -> RoleRead:
    service = WorkspacesService(session=session)
    role = await service.update_workspace_role(
        workspace_id=workspace.workspace_id,
        role_id=role_id,
        payload=payload,
        actor=actor,
    )
    return _serialize_role(role)


@router.delete(
    "/workspaces/{workspace_id}/roles/{role_id}",
    dependencies=[Security(require_csrf)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a workspace role",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "System roles cannot be deleted.",
            "model": ErrorMessage,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace roles.",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow managing roles.",
            "model": ErrorMessage,
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Role not found for this workspace.",
            "model": ErrorMessage,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Role is assigned or would violate governor guardrails.",
            "model": ErrorMessage,
        },
    },
)
async def delete_workspace_role(
    workspace: Annotated[WorkspaceProfile, Depends(get_workspace_profile)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Roles.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    role_id: Annotated[str, Path(min_length=1)],
) -> None:
    service = WorkspacesService(session=session)
    await service.delete_workspace_role(
        workspace_id=workspace.workspace_id, role_id=role_id
    )


@router.post(
    "/workspaces/{workspace_id}/members",
    dependencies=[Security(require_csrf)],
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
    workspace: Annotated[WorkspaceProfile, Depends(get_workspace_profile)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Members.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    *,
    payload: WorkspaceMemberCreate = WORKSPACE_MEMBER_BODY,
) -> WorkspaceMember:
    service = WorkspacesService(session=session)
    membership = await service.add_member(
        workspace_id=workspace.workspace_id,
        user_id=payload.user_id,
        role_ids=payload.role_ids or [],
    )
    return membership


@router.patch(
    "/workspaces/{workspace_id}",
    dependencies=[Security(require_csrf)],
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
    workspace: Annotated[WorkspaceProfile, Depends(get_workspace_profile)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Settings.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    *,
    payload: WorkspaceUpdate = WORKSPACE_UPDATE_BODY,
) -> WorkspaceProfile:
    service = WorkspacesService(session=session)
    workspace = await service.update_workspace(
        user=actor,
        workspace_id=workspace.workspace_id,
        name=payload.name,
        slug=payload.slug,
        settings=payload.settings,
    )
    return workspace


@router.delete(
    "/workspaces/{workspace_id}",
    dependencies=[Security(require_csrf)],
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
    workspace: Annotated[WorkspaceProfile, Depends(get_workspace_profile)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Delete"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DefaultResponse:
    service = WorkspacesService(session=session)
    await service.delete_workspace(workspace_id=workspace.workspace_id)
    return DefaultResponse.success("Workspace deleted")


@router.put(
    "/workspaces/{workspace_id}/members/{membership_id}/roles",
    dependencies=[Security(require_csrf)],
    response_model=WorkspaceMember,
    status_code=status.HTTP_200_OK,
    summary="Replace the set of roles for a workspace member",
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
    workspace: Annotated[WorkspaceProfile, Depends(get_workspace_profile)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Members.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    membership_id: str = Path(..., min_length=1, description="Membership identifier"),
    *,
    payload: WorkspaceMemberRolesUpdate = WORKSPACE_MEMBER_UPDATE_BODY,
) -> WorkspaceMember:
    service = WorkspacesService(session=session)
    membership = await service.assign_member_roles(
        workspace_id=workspace.workspace_id,
        membership_id=membership_id,
        payload=payload,
    )
    return membership


@router.delete(
    "/workspaces/{workspace_id}/members/{membership_id}",
    dependencies=[Security(require_csrf)],
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
    workspace: Annotated[WorkspaceProfile, Depends(get_workspace_profile)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Members.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    membership_id: str = Path(..., min_length=1, description="Membership identifier"),
) -> DefaultResponse:
    service = WorkspacesService(session=session)
    await service.remove_member(
        workspace_id=workspace.workspace_id, membership_id=membership_id
    )
    return DefaultResponse.success("Workspace member removed")


@router.post(
    "/workspaces/{workspace_id}/default",
    dependencies=[Security(require_csrf)],
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
    workspace: Annotated[WorkspaceProfile, Depends(get_workspace_profile)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkspaceDefaultSelection:
    service = WorkspacesService(session=session)
    selection = await service.set_default_workspace(
        workspace_id=workspace.workspace_id,
        user=actor,
    )
    return selection


__all__ = ["router"]
