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
        input_hash: str,
        trace_id: str,
    ) -> Job:
        job = Job(
            workspace_id=workspace_id,
            config_id=config_id,
            config_version_id=config_version_id,
            submitted_by_user_id=actor_id,
            status=JobStatus.QUEUED.value,
            queued_at=utc_now(),
            input_hash=input_hash,
            trace_id=trace_id,
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

    async def record_paths(
        self,
        job: Job,
        *,
        logs_uri: str | None = None,
        run_request_uri: str | None = None,
    ) -> Job:
        if logs_uri is not None:
            job.logs_uri = logs_uri
        if run_request_uri is not None:
            job.run_request_uri = run_request_uri
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def find_existing_job(
        self,
        *,
        workspace_id: str,
        config_version_id: str,
        input_hash: str,
    ) -> Job | None:
        stmt = (
            select(Job)
            .where(
                Job.workspace_id == workspace_id,
                Job.config_version_id == config_version_id,
                Job.input_hash == input_hash,
            )
            .options(selectinload(Job.config_version))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def reset_for_retry(self, job: Job, *, trace_id: str) -> Job:
        job.status = JobStatus.QUEUED.value
        job.queued_at = utc_now()
        job.started_at = None
        job.completed_at = None
        job.cancelled_at = None
        job.error_message = None
        job.artifact_uri = None
        job.output_uri = None
        job.logs_uri = None
        job.run_request_uri = None
        job.attempt = job.attempt + 1
        job.trace_id = trace_id
        await self._session.flush()
        await self._session.refresh(job)
        return job


__all__ = ["JobsRepository"]
