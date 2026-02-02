"""FastAPI dependency helpers for the workspaces feature."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Path

from ade_api.api.deps import ReadSessionDep, SettingsDep
from ade_api.core.http import require_authenticated
from ade_db.models import User

from .schemas import WorkspaceOut
from .service import WorkspacesService

def get_workspace_profile(
    user: Annotated[User, Depends(require_authenticated)],
    session: ReadSessionDep,
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
    return service.get_workspace_profile(user=user, workspace_id=workspace_id)


__all__ = ["get_workspace_profile"]
