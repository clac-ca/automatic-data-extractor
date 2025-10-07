"""FastAPI dependencies for workspace-aware routes."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import SecurityScopes
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

from ..auth.dependencies import bind_current_user
from ..users.models import User
from .schemas import WorkspaceProfile
from .service import WorkspaceScope, WorkspacesService, normalize_workspace_scopes


async def get_workspace_profile(
    current_user: Annotated[User, Depends(bind_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    workspace_id: Annotated[
        str,
        Path(
            min_length=1,
            description="Workspace identifier",
        ),
    ],
) -> WorkspaceProfile:
    """Return the active workspace membership profile for the request."""

    normalized = workspace_id.strip()
    if not normalized:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Workspace identifier required",
        )

    service = WorkspacesService(session=session)
    return await service.resolve_selection(user=current_user, workspace_id=normalized)


def _collect_scopes(
    values: Iterable[str | WorkspaceScope],
) -> frozenset[str]:
    try:
        return normalize_workspace_scopes(values)
    except ValueError as exc:  # pragma: no cover - defensive guard for misconfigurations
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid workspace scope configuration",
        ) from exc


def _enforce_workspace_permissions(
    *,
    workspace: WorkspaceProfile,
    permissions: Iterable[str | WorkspaceScope] | None = None,
) -> None:
    """Raise an HTTP error when the workspace lacks the required permissions."""

    required = _collect_scopes(permissions or [])
    if not required:
        return

    granted = _collect_scopes(workspace.permissions)
    if not required.issubset(granted):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )


async def require_workspace_access(
    security_scopes: SecurityScopes,
    workspace: Annotated[WorkspaceProfile, Depends(get_workspace_profile)],
) -> WorkspaceProfile:
    """Validate ``security_scopes`` against the resolved workspace profile."""

    _enforce_workspace_permissions(
        workspace=workspace, permissions=security_scopes.scopes
    )
    return workspace


__all__ = [
    "get_workspace_profile",
    "require_workspace_access",
]
