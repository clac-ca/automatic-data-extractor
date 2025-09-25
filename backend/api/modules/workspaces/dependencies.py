"""FastAPI dependencies for workspace-aware routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.service import service_dependency
from ...db.session import get_session
from ..auth.dependencies import bind_current_user
from ..users.models import User
from .schemas import WorkspaceContext, WorkspaceProfile
from .service import WorkspacesService

get_workspaces_service = service_dependency(WorkspacesService)
WorkspacePath = Annotated[
    str,
    Path(min_length=1, description="Workspace identifier"),
]
UserDependency = Annotated[User, Depends(bind_current_user)]
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
WorkspaceServiceDependency = Annotated[WorkspacesService, Depends(get_workspaces_service)]


async def bind_workspace_context(
    request: Request,
    current_user: UserDependency,
    session: SessionDependency,
    service: WorkspaceServiceDependency,
    workspace_id: WorkspacePath,
) -> WorkspaceContext:
    """Resolve and attach the workspace context to the request."""

    selection = await service.resolve_selection(
        user=current_user, workspace_id=workspace_id
    )
    request.state.current_workspace = selection.workspace
    request.state.current_permissions = frozenset(selection.workspace.permissions)
    return selection


async def list_user_workspaces(
    current_user: UserDependency,
    session: SessionDependency,
    service: WorkspaceServiceDependency,
) -> list[WorkspaceProfile]:
    """Return all workspace memberships for the authenticated user."""

    return await service.list_memberships(user=current_user)


__all__ = [
    "bind_workspace_context",
    "get_workspaces_service",
    "list_user_workspaces",
]
