"""FastAPI dependencies for config package operations."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.shared.core.config import Settings, get_app_settings
from backend.app.shared.db.session import get_session

from .service import ConfigsService


async def get_configs_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> ConfigsService:
    """Construct a request-scoped ``ConfigsService``."""

    return ConfigsService(session=session, settings=settings)


__all__ = ["get_configs_service"]
