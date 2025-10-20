"""FastAPI dependencies for the jobs feature."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.settings import get_app_settings
from backend.app.db.session import get_session
from backend.app.platform.config import Settings

from .service import JobsService


def get_jobs_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> JobsService:
    """Return a request-scoped jobs service."""

    return JobsService(session=session, settings=settings)


__all__ = ["get_jobs_service"]
