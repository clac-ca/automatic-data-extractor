"""SQLite-backed queue implementation that polls the ``jobs`` table."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.features.jobs.models import Job

from .base import QueueAdapter, QueueMessage


class SQLitePollingQueue(QueueAdapter):
    """Poll jobs stored in SQLite and expose them as queue messages."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def enqueue(
        self,
        name: str,
        payload: Mapping[str, Any],
        *,
        correlation_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> QueueMessage:
        job_id = _require_job_id(payload)
        async with self._session_factory() as session:
            job = await session.get(Job, job_id)
            if job is None:
                raise ValueError(f"Job '{job_id}' not found.")
            now = datetime.now(tz=UTC)
            queue_meta = dict(job.metrics.get("queue") or {})
            queue_meta.update(
                {
                    "name": name,
                    "payload": dict(payload),
                    "metadata": dict(metadata or {}),
                    "correlation_id": correlation_id,
                    "enqueued_at": now.isoformat(),
                    "attempts": int(queue_meta.get("attempts", 0)),
                    "last_error": None,
                }
            )
            job.metrics["queue"] = queue_meta
            job.status = "pending"
            await session.flush()
            await session.commit()
        return QueueMessage(
            id=job_id,
            name=name,
            payload=dict(payload),
            enqueued_at=now,
            attempts=int(queue_meta.get("attempts", 0)),
        )

    async def claim(self) -> QueueMessage | None:
        async with self._session_factory() as session:
            stmt = (
                select(Job)
                .where(Job.status == "pending")
                .order_by(Job.created_at.asc(), Job.id.asc())
                .limit(1)
            )
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            if job is None:
                return None

            now = datetime.now(tz=UTC)
            queue_meta = dict(job.metrics.get("queue") or {})
            attempts = int(queue_meta.get("attempts", 0)) + 1
            queue_meta["attempts"] = attempts
            queue_meta["claimed_at"] = now.isoformat()
            job.metrics["queue"] = queue_meta
            job.status = "running"
            await session.flush()
            await session.commit()

        payload = dict(queue_meta.get("payload") or {})
        name = str(queue_meta.get("name") or "job")
        enqueued_at = _parse_iso_datetime(queue_meta.get("enqueued_at")) or now
        return QueueMessage(
            id=job.job_id,
            name=name,
            payload=payload,
            enqueued_at=enqueued_at,
            attempts=attempts,
        )

    async def ack(self, message: QueueMessage) -> None:
        async with self._session_factory() as session:
            job = await session.get(Job, message.id)
            if job is None:
                return
            queue_meta = dict(job.metrics.get("queue") or {})
            queue_meta["completed_at"] = datetime.now(tz=UTC).isoformat()
            job.metrics["queue"] = queue_meta
            job.status = "succeeded"
            await session.flush()
            await session.commit()

    async def fail(self, message: QueueMessage, *, reason: str | None = None) -> None:
        async with self._session_factory() as session:
            job = await session.get(Job, message.id)
            if job is None:
                return
            queue_meta = dict(job.metrics.get("queue") or {})
            queue_meta["last_error"] = reason
            queue_meta["failed_at"] = datetime.now(tz=UTC).isoformat()
            job.metrics["queue"] = queue_meta
            job.status = "failed"
            await session.flush()
            await session.commit()


def _require_job_id(payload: Mapping[str, Any]) -> str:
    job_id = payload.get("job_id")
    if not job_id:
        raise ValueError("payload must include 'job_id'.")
    return str(job_id)


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


__all__ = ["SQLitePollingQueue"]

