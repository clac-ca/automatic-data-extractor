"""HTTP endpoints for role and permission management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

from ..auth.dependencies import bind_current_user
from ..users.models import User
from ..workspaces.service import WorkspacesService
from .models import Permission
from .registry import PermissionScope
from .schemas import PermissionRead
from .service import (
    authorize_global,
    authorize_workspace,
    get_global_permissions_for_user,
)


router = APIRouter(tags=["roles"])


@router.get(
    "/permissions",
    response_model=list[PermissionRead],
    summary="List permission catalog entries",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Authentication required to list permissions.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Caller lacks permission catalog access.",
        },
    },
)
async def list_permissions(
    scope: PermissionScope = Query(
        ..., description="Permission scope to list", examples={"default": {"value": "workspace"}}
    ),
    workspace_id: str | None = Query(
        default=None,
        min_length=1,
        description="Workspace identifier required when scope=workspace.",
    ),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(bind_current_user),
) -> list[PermissionRead]:
    """Return permission registry entries filtered by ``scope``."""

    if scope == "global":
        granted = await get_global_permissions_for_user(
            session=session, user=current_user
        )
        decision = authorize_global(
            granted=granted, required=["Roles.Read.All"]
        )
        if not decision.is_authorized:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Insufficient global permissions",
            )
    else:
        if workspace_id is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="workspace_id is required for workspace permissions",
            )
        service = WorkspacesService(session=session)
        profile = await service.resolve_selection(
            user=current_user, workspace_id=workspace_id
        )
        decision = authorize_workspace(
            granted=profile.permissions, required=["Workspace.Roles.Read"]
        )
        if not decision.is_authorized:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Insufficient workspace permissions",
            )

    stmt = (
        select(Permission)
        .where(Permission.scope == scope)
        .order_by(Permission.key)
    )
    result = await session.execute(stmt)
    permissions = result.scalars().all()
    return [PermissionRead.model_validate(permission) for permission in permissions]


__all__ = ["router"]

