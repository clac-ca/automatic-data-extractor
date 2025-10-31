"""Database helpers for job persistence."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.shared.core.time import utc_now

from .models import Job, JobStatus


class JobsRepository:
    """Manage CRUD operations for jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_job(
        self,
        *,
        workspace_id: str,
        config_id: str,
        config_version_id: str,
        actor_id: str | None,
    ) -> Job:
        job = Job(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            submitted_by_user_id=actor_id,
            status=JobStatus.QUEUED.value,
            queued_at=utc_now(),
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def get_job(self, *, workspace_id: str, job_id: str) -> Job | None:
        stmt = (
            select(Job)
            .where(Job.workspace_id == workspace_id, Job.id == job_id)
            .options(selectinload(Job.config_version))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        job: Job,
        *,
        status: JobStatus,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error_message: str | None = None,
        artifact_uri: str | None = None,
        output_uri: str | None = None,
    ) -> Job:
        job.status = status.value
        if started_at is not None:
            job.started_at = started_at
        if completed_at is not None:
            job.completed_at = completed_at
        job.error_message = error_message
        job.artifact_uri = artifact_uri or job.artifact_uri
        job.output_uri = output_uri or job.output_uri
        await self._session.flush()
        await self._session.refresh(job)
        return job


__all__ = ["JobsRepository"]
