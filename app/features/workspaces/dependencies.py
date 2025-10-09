"""FastAPI dependencies for workspace-aware routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

from ..auth.dependencies import get_current_user
from ..users.models import User
from .schemas import WorkspaceProfile
from .service import WorkspacesService


async def get_workspace_profile(
    current_user: Annotated[User, Depends(get_current_user)],
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
    return await service.get_workspace_profile(
        user=current_user, workspace_id=normalized
    )


__all__ = [
    "get_workspace_profile",
]
