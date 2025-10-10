"""Shared FastAPI dependency aliases for ADE API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ade.db.session import get_session
from ade.features.auth.dependencies import get_current_identity, get_current_user
from ade.features.auth.service import AuthenticatedIdentity
from ade.features.users.models import User

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CurrentIdentity = Annotated[AuthenticatedIdentity, Depends(get_current_identity)]
CurrentUser = Annotated[User, Depends(get_current_user)]

__all__ = [
    "SessionDependency",
    "CurrentIdentity",
    "CurrentUser",
]
