"""Data access helpers for job records."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Job, JobStatus

__all__ = ["JobRunSummary", "JobsRepository"]


@dataclass(slots=True)
class JobRunSummary:
    """Minimal snapshot of the latest job run for a document."""

    job_id: str
    status: str
    run_at: datetime | None
    message: str | None


class JobsRepository:
    """Encapsulate database access for job persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def base_query(self) -> Select[tuple[Job]]:
        return select(Job).options(selectinload(Job.submitted_by_user))

    async def get_job(
        self,
        *,
        workspace_id: str,
        job_id: str,
    ) -> Job | None:
        stmt = (
            self.base_query()
            .where(Job.workspace_id == workspace_id, Job.id == job_id)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        *,
        workspace_id: str,
        status: JobStatus | None = None,
        input_document_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Job]:
        stmt = self.base_query().where(Job.workspace_id == workspace_id)
        if status is not None:
            stmt = stmt.where(Job.status == status)
        stmt = stmt.order_by(Job.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        jobs = list(result.scalars())
        if input_document_id:
            jobs = [
                job
                for job in jobs
                if any(
                    isinstance(doc, dict)
                    and doc.get("document_id") == input_document_id
                    for doc in (job.input_documents or [])
                )
            ]
        return jobs

    async def latest_runs_for_documents(
        self,
        *,
        workspace_id: str,
        document_ids: Sequence[str],
        batch_size: int = 200,
    ) -> dict[str, JobRunSummary]:
        """Return the most recent job per document within ``workspace_id``."""

        deduped_ids = [doc_id for doc_id in dict.fromkeys(document_ids) if doc_id]
        if not deduped_ids:
            return {}

        remaining = set(deduped_ids)
        summaries: dict[str, JobRunSummary] = {}

        sort_expr = func.coalesce(
            Job.completed_at,
            Job.started_at,
            Job.updated_at,
            Job.queued_at,
        ).desc()
        offset = 0

        while remaining:
            stmt: Select[tuple[Job]] = (
                select(Job)
                .where(Job.workspace_id == workspace_id)
                .order_by(sort_expr, Job.id.desc())
                .limit(batch_size)
                .offset(offset)
            )
            result = await self._session.execute(stmt)
            rows = result.scalars().all()
            if not rows:
                break

            offset += batch_size

            for job in rows:
                documents = job.input_documents or []
                if not isinstance(documents, list):
                    continue

                for entry in documents:
                    doc_id = entry.get("document_id") if isinstance(entry, dict) else None
                    if doc_id is None or doc_id not in remaining:
                        continue

                    if doc_id in summaries:
                        continue

                    run_timestamp = (
                        job.completed_at
                        or job.started_at
                        or job.updated_at
                        or job.queued_at
                    )
                    status_value = (
                        job.status.value
                        if isinstance(job.status, JobStatus)
                        else str(job.status)
                    )
                    summaries[doc_id] = JobRunSummary(
                        job_id=job.id,
                        status=status_value,
                        run_at=run_timestamp,
                        message=job.error_message,
                    )
                    remaining.discard(doc_id)

                if not remaining:
                    break

        return summaries
