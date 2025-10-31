"""FastAPI dependencies for job orchestration."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.shared.core.config import Settings, get_app_settings
from backend.app.shared.db.session import get_session

from .service import JobsService


async def get_jobs_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> JobsService:
    """Construct a request-scoped ``JobsService``."""

    return JobsService(session=session, settings=settings)


__all__ = ["get_jobs_service"]
