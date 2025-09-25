"""Routes for workspace membership and context resolution."""

from fastapi import APIRouter, Body, Depends, Path, status
from fastapi_utils.cbv import cbv
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.responses import DefaultResponse
from ...db.session import get_session
from ..auth.dependencies import bind_current_user
from ..auth.security import access_control
from ..users.models import User
from .dependencies import bind_workspace_context, get_workspaces_service
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


@cbv(router)
class WorkspaceRoutes:
    current_user: User = Depends(bind_current_user)  # noqa: B008
    session: AsyncSession = Depends(get_session)  # noqa: B008
    service: WorkspacesService = Depends(get_workspaces_service)  # noqa: B008

    @router.post(
        "/workspaces",
        response_model=WorkspaceProfile,
        status_code=status.HTTP_201_CREATED,
        summary="Create a new workspace",
        response_model_exclude_none=True,
    )
    @access_control(require_admin=True)
    async def create_workspace(
        self, payload: WorkspaceCreate = WORKSPACE_CREATE_BODY
    ) -> WorkspaceProfile:
        workspace = await self.service.create_workspace(
            user=self.current_user,
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
    )
    async def list_workspaces(self) -> list[WorkspaceProfile]:
        memberships = await self.service.list_memberships(user=self.current_user)
        return memberships

    @router.get(
        "/workspaces/{workspace_id}",
        response_model=WorkspaceContext,
        status_code=status.HTTP_200_OK,
        summary="Retrieve workspace context by identifier",
        response_model_exclude_none=True,
    )
    async def read_workspace(
        self,
        selection: WorkspaceContext = Depends(bind_workspace_context),  # noqa: B008
    ) -> WorkspaceContext:
        return selection

    @router.get(
        "/workspaces/{workspace_id}/members",
        response_model=list[WorkspaceMember],
        status_code=status.HTTP_200_OK,
        summary="List members within the workspace",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:members:read"}, require_workspace=True)
    async def list_members(
        self,
        workspace_id: str,
        _: WorkspaceContext = Depends(bind_workspace_context),  # noqa: B008
    ) -> list[WorkspaceMember]:
        memberships = await self.service.list_members(workspace_id=workspace_id)
        return memberships

    @router.post(
        "/workspaces/{workspace_id}/members",
        response_model=WorkspaceMember,
        status_code=status.HTTP_201_CREATED,
        summary="Add a member to a workspace",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:members:manage"}, require_workspace=True)
    async def add_member(
        self,
        workspace_id: str,
        payload: WorkspaceMemberCreate = WORKSPACE_MEMBER_BODY,
        _: WorkspaceContext = Depends(bind_workspace_context),  # noqa: B008
    ) -> WorkspaceMember:
        membership = await self.service.add_member(
            workspace_id=workspace_id,
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
    )
    @access_control(permissions={"workspace:settings:manage"}, require_workspace=True)
    async def update_workspace(
        self,
        workspace_id: str,
        payload: WorkspaceUpdate = WORKSPACE_UPDATE_BODY,
        _: WorkspaceContext = Depends(bind_workspace_context),  # noqa: B008
    ) -> WorkspaceProfile:
        workspace = await self.service.update_workspace(
            user=self.current_user,
            workspace_id=workspace_id,
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
    )
    @access_control(permissions={"workspace:settings:manage"}, require_workspace=True)
    async def delete_workspace(
        self,
        workspace_id: str,
        _: WorkspaceContext = Depends(bind_workspace_context),  # noqa: B008
    ) -> DefaultResponse:
        await self.service.delete_workspace(workspace_id=workspace_id)
        return DefaultResponse.success("Workspace deleted")

    @router.patch(
        "/workspaces/{workspace_id}/members/{membership_id}",
        response_model=WorkspaceMember,
        status_code=status.HTTP_200_OK,
        summary="Update a workspace member",
        response_model_exclude_none=True,
    )
    @access_control(permissions={"workspace:members:manage"}, require_workspace=True)
    async def update_member(
        self,
        workspace_id: str,
        membership_id: str = Path(..., min_length=1, description="Membership identifier"),
        payload: WorkspaceMemberUpdate = WORKSPACE_MEMBER_UPDATE_BODY,
        _: WorkspaceContext = Depends(bind_workspace_context),  # noqa: B008
    ) -> WorkspaceMember:
        membership = await self.service.update_member_role(
            workspace_id=workspace_id,
            membership_id=membership_id,
            role=payload.role,
        )
        return membership

    @router.delete(
        "/workspaces/{workspace_id}/members/{membership_id}",
        response_model=DefaultResponse,
        status_code=status.HTTP_200_OK,
        summary="Remove a workspace member",
    )
    @access_control(permissions={"workspace:members:manage"}, require_workspace=True)
    async def remove_member(
        self,
        workspace_id: str,
        membership_id: str = Path(..., min_length=1, description="Membership identifier"),
        _: WorkspaceContext = Depends(bind_workspace_context),  # noqa: B008
    ) -> DefaultResponse:
        await self.service.remove_member(
            workspace_id=workspace_id,
            membership_id=membership_id,
        )
        return DefaultResponse.success("Workspace member removed")

    @router.post(
        "/workspaces/{workspace_id}/default",
        response_model=WorkspaceDefaultSelection,
        status_code=status.HTTP_200_OK,
        summary="Mark a workspace as the caller's default",
    )
    @access_control(require_workspace=True)
    async def set_default_workspace(
        self,
        workspace_id: str,
        _: WorkspaceContext = Depends(bind_workspace_context),  # noqa: B008
    ) -> WorkspaceDefaultSelection:
        selection = await self.service.set_default_workspace(
            user=self.current_user,
            workspace_id=workspace_id,
        )
        return selection


__all__ = ["router"]
