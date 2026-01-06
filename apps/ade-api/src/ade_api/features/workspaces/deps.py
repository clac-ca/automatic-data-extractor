"""FastAPI dependency helpers for the workspaces feature."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.core.http import require_authenticated
from ade_api.db import get_db_session
from ade_api.models import User
from ade_api.settings import Settings, get_settings

from .schemas import WorkspaceOut
from .service import WorkspacesService

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_workspace_profile(
    user: Annotated[User, Depends(require_authenticated)],
    session: SessionDep,
    settings: SettingsDep,
    workspace_id: Annotated[
        UUID,
        Path(
            description="Workspace identifier",
            alias="workspaceId",
        ),
    ],
) -> WorkspaceOut:
    service = WorkspacesService(session=session, settings=settings)
    return await service.get_workspace_profile(user=user, workspace_id=workspace_id)


__all__ = ["get_workspace_profile"]
