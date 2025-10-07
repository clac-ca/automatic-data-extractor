"""Shared FastAPI dependency aliases for ADE API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.auth.dependencies import bind_current_principal, bind_current_user
from app.features.auth.service import AuthenticatedIdentity
from app.features.users.models import User

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CurrentIdentity = Annotated[AuthenticatedIdentity, Depends(bind_current_principal)]
CurrentUser = Annotated[User, Depends(bind_current_user)]

__all__ = [
    "SessionDependency",
    "CurrentIdentity",
    "CurrentUser",
]
