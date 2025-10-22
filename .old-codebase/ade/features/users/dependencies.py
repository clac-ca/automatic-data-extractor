"""FastAPI dependencies for the users feature."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ade.db.session import get_session

from .service import UsersService


def get_users_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UsersService:
    """Return a users service bound to the current database session."""

    return UsersService(session=session)


__all__ = ["get_users_service"]
