"""FastAPI dependency helpers for the workspaces feature."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.core.http import require_authenticated
from ade_api.db.session import get_session
from ade_api.models import User

from .schemas import WorkspaceOut
from .service import WorkspacesService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_workspace_profile(
    user: Annotated[User, Depends(require_authenticated)],
    session: SessionDep,
    workspace_id: Annotated[
        UUID,
        Path(
            description="Workspace identifier",
            alias="workspaceId",
        ),
    ],
) -> WorkspaceOut:
    service = WorkspacesService(session=session)
    return await service.get_workspace_profile(user=user, workspace_id=workspace_id)


__all__ = ["get_workspace_profile"]
