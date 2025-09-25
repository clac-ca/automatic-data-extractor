"""Routes for workspace membership and context resolution."""

from fastapi import APIRouter, Body, Depends, status
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
    WorkspaceMember,
    WorkspaceMemberCreate,
    WorkspaceProfile,
)
from .service import WorkspacesService

router = APIRouter(tags=["workspaces"])

WORKSPACE_MEMBER_BODY = Body(...)


@cbv(router)
class WorkspaceRoutes:
    current_user: User = Depends(bind_current_user)  # noqa: B008
    session: AsyncSession = Depends(get_session)  # noqa: B008
    service: WorkspacesService = Depends(get_workspaces_service)  # noqa: B008

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
        response_model=DefaultResponse,
        status_code=status.HTTP_200_OK,
        summary="Example endpoint requiring workspace permission",
    )
    @access_control(permissions={"workspace:members:read"}, require_workspace=True)
    async def list_members(
        self,
        _: WorkspaceContext = Depends(bind_workspace_context),  # noqa: B008
    ) -> DefaultResponse:
        return DefaultResponse.success("Access granted")

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


__all__ = ["router"]
