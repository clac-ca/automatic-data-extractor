"""Dependency wiring for configuration engine v0.4 service placeholders."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.shared.db.session import get_async_session

from .service import ConfigService


async def get_config_service(
    session: AsyncSession = Depends(get_async_session),
) -> ConfigService:
    return ConfigService(session=session)


__all__ = ["get_config_service"]
