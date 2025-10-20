"""Data persistence helpers for job records."""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Job


class JobsRepository:
    """Encapsulate database access for workspace jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def base_query(self, workspace_id: str) -> Select[tuple[Job]]:
        """Return the base selectable for workspace jobs."""

        return select(Job).where(Job.workspace_id == workspace_id)

    async def list_jobs(
        self,
        *,
        workspace_id: str,
        limit: int,
        offset: int,
        status: str | None = None,
        input_document_id: str | None = None,
    ) -> list[Job]:
        """Return jobs ordered by recency with optional filtering."""

        stmt = (
            self.base_query(workspace_id)
            .order_by(Job.created_at.desc(), Job.id.desc())
            .offset(offset)
            .limit(limit)
        )
        if status is not None:
            stmt = stmt.where(Job.status == status)
        if input_document_id is not None:
            stmt = stmt.where(Job.input_document_id == input_document_id)

        result = await self._session.execute(stmt)
        return list(result.scalars())

    async def get_job(self, *, workspace_id: str, job_id: str) -> Job | None:
        """Return a single job for ``workspace_id`` when it exists."""

        stmt = self.base_query(workspace_id).where(Job.id == job_id).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


__all__ = ["JobsRepository"]

