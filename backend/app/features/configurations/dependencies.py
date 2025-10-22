"""FastAPI dependencies for configuration management."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.shared.db.session import get_session
from .service import ConfigurationsService


def get_configurations_service(
    session: Annotated[AsyncSession, Depends(get_session)]
) -> ConfigurationsService:
    """Provide a request-scoped ConfigurationsService instance."""

    return ConfigurationsService(session=session)


__all__ = ["get_configurations_service"]
