"""FastAPI dependencies for workspace-aware routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path, Request, status

from app.core.service import service_dependency

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
WorkspaceServiceDependency = Annotated[WorkspacesService, Depends(get_workspaces_service)]


async def bind_workspace_context(
    request: Request,
    current_user: UserDependency,
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


WorkspaceContextDependency = Annotated[
    WorkspaceContext, Depends(bind_workspace_context)
]


async def require_workspace_context(
    workspace_id: WorkspacePath,
    selection: WorkspaceContextDependency,
) -> WorkspaceContext:
    """Return the active workspace context and validate the path parameter."""

    resolved_id = selection.workspace.workspace_id
    if resolved_id != workspace_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Workspace path does not match the active selection",
        )
    return selection


async def list_user_workspaces(
    current_user: UserDependency,
    service: WorkspaceServiceDependency,
) -> list[WorkspaceProfile]:
    """Return all workspace memberships for the authenticated user."""

    return await service.list_memberships(user=current_user)


__all__ = [
    "bind_workspace_context",
    "get_workspaces_service",
    "require_workspace_context",
    "list_user_workspaces",
]
