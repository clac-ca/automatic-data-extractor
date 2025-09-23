"""FastAPI dependencies for workspace-aware routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.service import service_dependency
from ...db.session import get_session
from ..auth.dependencies import bind_current_user
from ..users.models import User
from .schemas import WorkspaceContext, WorkspaceProfile
from .service import WorkspacesService


get_workspaces_service = service_dependency(WorkspacesService)
WorkspaceHeader = Annotated[str | None, Header(alias="X-Workspace-ID")]


async def bind_workspace_context(
    request: Request,
    current_user: User = Depends(bind_current_user),
    session: AsyncSession = Depends(get_session),
    workspace_header: WorkspaceHeader = None,
    service: WorkspacesService = Depends(get_workspaces_service),
) -> WorkspaceContext:
    """Resolve and attach the workspace context to the request."""

    selection = await service.resolve_selection(
        user=current_user, workspace_id=workspace_header
    )
    request.state.current_workspace = selection.workspace
    request.state.current_permissions = frozenset(selection.workspace.permissions)
    return selection


async def list_user_workspaces(
    current_user: User = Depends(bind_current_user),
    session: AsyncSession = Depends(get_session),
    service: WorkspacesService = Depends(get_workspaces_service),
) -> list[WorkspaceProfile]:
    """Return all workspace memberships for the authenticated user."""

    return await service.list_memberships(user=current_user)


__all__ = [
    "WorkspaceHeader",
    "bind_workspace_context",
    "get_workspaces_service",
    "list_user_workspaces",
]
