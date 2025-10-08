"""FastAPI dependencies for global authorization checks."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import SecurityScopes
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

from ..auth.dependencies import bind_current_user
from ..users.models import User
from .service import (
    AuthorizationError,
    authorize_global,
    get_global_permissions_for_user,
)


async def require_global_access(
    security_scopes: SecurityScopes,
    user: Annotated[User, Depends(bind_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Ensure ``user`` has the requested global permissions."""

    required = tuple(security_scopes.scopes)
    if not required:
        return user

    granted = await get_global_permissions_for_user(session=session, user=user)

    try:
        decision = authorize_global(granted=granted, required=required)
    except AuthorizationError as exc:  # pragma: no cover - configuration guardrail
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid global permission configuration",
        ) from exc

    if decision.is_authorized:
        return user

    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        detail="Insufficient global permissions",
    )


__all__ = ["require_global_access"]
