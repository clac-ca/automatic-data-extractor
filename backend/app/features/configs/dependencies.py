"""FastAPI dependencies for the configuration engine."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.shared.db.session import get_session

from .service import ConfigService


async def get_config_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConfigService:
    return ConfigService(session=session)


__all__ = ["get_config_service"]
