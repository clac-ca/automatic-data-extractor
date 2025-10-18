"""FastAPI dependencies for system settings."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ade.db.session import get_session

from .service import SystemSettingsService


def get_system_settings_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SystemSettingsService:
    """Return a request-scoped system settings service."""

    return SystemSettingsService(session=session)


__all__ = ["get_system_settings_service"]
