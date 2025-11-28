from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.shared.core.responses import DefaultResponse
from ade_api.shared.db.session import get_session
from ade_api.shared.dependency import (
    get_workspace_profile,
    require_authenticated,
    require_csrf,
    require_global,
    require_workspace,
)
from ade_api.shared.pagination import PageParams, paginate_sequence

from ..roles.models import Role, ScopeType
from ..roles.schemas import RoleCreate, RoleOut, RolePage, RoleUpdate
from ..roles.service import paginate_roles
from ..users.models import User
from .schemas import (
    WorkspaceCreate,
    WorkspaceDefaultSelectionOut,
    WorkspaceMemberCreate,
    WorkspaceMemberOut,
    WorkspaceMemberPage,
    WorkspaceMemberRolesUpdate,
    WorkspaceOut,
    WorkspacePage,
    WorkspaceUpdate,
)
from .service import WorkspacesService

router = APIRouter(tags=["workspaces"], dependencies=[Security(require_authenticated)])

WORKSPACE_MEMBER_BODY = Body(...)
WORKSPACE_CREATE_BODY = Body(...)
WORKSPACE_UPDATE_BODY = Body(...)
WORKSPACE_MEMBER_UPDATE_BODY = Body(...)


def _serialize_role(role: Role) -> RoleOut:
    return RoleOut(
        id=role.id,
        slug=role.slug,
        name=role.name,
        description=role.description,
        scope_type=role.scope_type,
        scope_id=role.scope_id,
        permissions=[
            permission.permission.key
            for permission in role.permissions
            if permission.permission is not None
        ],
        built_in=role.built_in,
        editable=role.editable,
    )


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
        Security(require_global("Workspaces.Create")),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    *,
    payload: WorkspaceCreate = WORKSPACE_CREATE_BODY,
) -> WorkspaceOut:
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
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkspacePage:
    service = WorkspacesService(session=session)
    memberships = await service.list_memberships(user=current_user)
    page_result = paginate_sequence(
        memberships,
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
            require_workspace("Workspace.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
) -> WorkspaceOut:
    return workspace


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=WorkspaceMemberPage,
    status_code=status.HTTP_200_OK,
    summary="List members within the workspace",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list workspace members.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow member access.",
        },
    },
)
async def list_members(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Members.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    page: Annotated[PageParams, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkspaceMemberPage:
    service = WorkspacesService(session=session)
    memberships = await service.list_members(
        workspace_id=workspace.id
    )
    page_result = paginate_sequence(
        memberships,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    return WorkspaceMemberPage(**page_result.model_dump())


@router.get(
    "/workspaces/{workspace_id}/roles",
    response_model=RolePage,
    status_code=status.HTTP_200_OK,
    summary="List roles available to the workspace",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list workspace roles.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow viewing role definitions.",
        },
    },
)
async def list_workspace_roles(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
    _actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Roles.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    page: Annotated[PageParams, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RolePage:
    role_page = await paginate_roles(
        session=session,
        scope_type=ScopeType.WORKSPACE,
        scope_id=workspace.id,
        page=page.page,
        page_size=page.page_size,
        include_total=page.include_total,
    )
    return RolePage(
        items=[_serialize_role(role) for role in role_page.items],
        page=role_page.page,
        page_size=role_page.page_size,
        has_next=role_page.has_next,
        has_previous=role_page.has_previous,
        total=role_page.total,
    )


@router.post(
    "/workspaces/{workspace_id}/roles",
    dependencies=[Security(require_csrf)],
    response_model=RoleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace role",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "System roles cannot be managed via this endpoint.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace roles.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow managing roles.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Role slug already exists or conflicts with a system role.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid role name, slug, or permissions.",
        },
    },
)
async def create_workspace_role(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
    actor: Annotated[
        User,
        Security(
            require_workspace("Workspace.Roles.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    payload: RoleCreate,
) -> RoleOut:
    service = WorkspacesService(session=session)
    role = await service.create_workspace_role(
        workspace_id=workspace.id,
        payload=payload,
        actor=actor,
    )
    return _serialize_role(role)


@router.put(
    "/workspaces/{workspace_id}/roles/{role_id}",
    dependencies=[Security(require_csrf)],
    response_model=RoleOut,
    status_code=status.HTTP_200_OK,
    summary="Update a workspace role",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "System roles cannot be modified.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace roles.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow managing roles.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Role not found for this workspace.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Operation would violate governor guardrails.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Invalid role payload.",
        },
    },
)
async def update_workspace_role(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
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
) -> RoleOut:
    service = WorkspacesService(session=session)
    role = await service.update_workspace_role(
        workspace_id=workspace.id,
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
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace roles.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow managing roles.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Role not found for this workspace.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "Role is assigned or would violate governor guardrails.",
        },
    },
)
async def delete_workspace_role(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
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
        workspace_id=workspace.id, role_id=role_id
    )


@router.post(
    "/workspaces/{workspace_id}/members",
    dependencies=[Security(require_csrf)],
    response_model=WorkspaceMemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member to a workspace",
    response_model_exclude_none=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace members.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow member management.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Workspace or user not found.",
        },
        status.HTTP_409_CONFLICT: {
            "description": "User is already a member of the workspace.",
        },
    },
)
async def add_member(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
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
) -> WorkspaceMemberOut:
    service = WorkspacesService(session=session)
    membership = await service.add_member(
        workspace_id=workspace.id,
        user_id=payload.user_id,
        role_ids=payload.role_ids or [],
    )
    return membership


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
            require_workspace("Workspace.Settings.ReadWrite"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    *,
    payload: WorkspaceUpdate = WORKSPACE_UPDATE_BODY,
) -> WorkspaceOut:
    service = WorkspacesService(session=session)
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
    response_model=DefaultResponse,
    status_code=status.HTTP_200_OK,
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
            require_workspace("Workspace.Delete"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DefaultResponse:
    service = WorkspacesService(session=session)
    await service.delete_workspace(workspace_id=workspace.id)
    return DefaultResponse.success("Workspace deleted")


@router.put(
    "/workspaces/{workspace_id}/members/{membership_id}/roles",
    dependencies=[Security(require_csrf)],
    response_model=WorkspaceMemberOut,
    status_code=status.HTTP_200_OK,
    summary="Replace the set of roles for a workspace member",
    response_model_exclude_none=True,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Workspace must retain at least one owner.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace members.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow member management.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Membership not found within the workspace.",
        },
    },
)
async def update_member(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
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
) -> WorkspaceMemberOut:
    service = WorkspacesService(session=session)
    membership = await service.assign_member_roles(
        workspace_id=workspace.id,
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
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to manage workspace members.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Workspace permissions do not allow member management.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Membership not found within the workspace.",
        },
    },
)
async def remove_member(
    workspace: Annotated[WorkspaceOut, Depends(get_workspace_profile)],
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
        workspace_id=workspace.id, membership_id=membership_id
    )
    return DefaultResponse.success("Workspace member removed")


@router.post(
    "/workspaces/{workspace_id}/default",
    dependencies=[Security(require_csrf)],
    response_model=WorkspaceDefaultSelectionOut,
    status_code=status.HTTP_200_OK,
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
            require_workspace("Workspace.Read"),
            scopes=["{workspace_id}"],
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkspaceDefaultSelectionOut:
    service = WorkspacesService(session=session)
    selection = await service.set_default_workspace(
        workspace_id=workspace.id,
        user=actor,
    )
    return selection


__all__ = ["router"]
