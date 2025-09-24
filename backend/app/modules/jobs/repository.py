"""Data access helpers for jobs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Job


class JobsRepository:
    """Query helper responsible for job lookups."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_jobs(
        self,
        *,
        input_document_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Job]:
        """Return jobs ordered by recency."""

        stmt: Select[tuple[Job]] = select(Job).order_by(
            Job.created_at.desc(),
            Job.job_id.desc(),
        )
        if input_document_id is not None:
            stmt = stmt.where(Job.input_document_id == input_document_id)
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_job(self, job_id: str) -> Job | None:
        """Return the job identified by ``job_id`` when available."""

        return await self._session.get(Job, job_id)

    async def create_job(
        self,
        *,
        job_id: str,
        document_type: str,
        configuration_id: str,
        configuration_version: int,
        status: str,
        created_by: str,
        input_document_id: str,
        metrics: Mapping[str, Any] | None = None,
        logs: list[Mapping[str, Any]] | None = None,
    ) -> Job:
        """Persist a new job record and return the ORM instance."""

        job = Job(
            job_id=job_id,
            document_type=document_type,
            configuration_id=configuration_id,
            configuration_version=configuration_version,
            status=status,
            created_by=created_by,
            input_document_id=input_document_id,
            metrics=dict(metrics or {}),
            logs=[dict(entry) for entry in logs or []],
        )

        self._session.add(job)
        await self._session.flush()
        return job


__all__ = ["JobsRepository"]
