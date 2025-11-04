"""FastAPI dependencies for job orchestration."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.shared.core.config import Settings, get_app_settings
from backend.app.shared.db.session import get_session

from .manager import JobQueueManager
from .service import JobsService


def _get_job_queue(request: Request) -> JobQueueManager | None:
    return getattr(request.app.state, "job_queue", None)


async def get_jobs_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    queue: Annotated[JobQueueManager | None, Depends(_get_job_queue)],
) -> JobsService:
    """Construct a request-scoped ``JobsService``."""

    return JobsService(session=session, settings=settings, queue=queue)


__all__ = ["get_jobs_service"]
