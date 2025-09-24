"""Task queue subscribers for job processing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...core.message_hub import MessageHub
from ...core.task_queue import TaskMessage, TaskQueue
from ...db.session import get_sessionmaker
from ..events.recorder import persist_event
from ..results.models import ExtractedTable
from ..results.repository import ExtractedTablesRepository
from .models import Job
from backend.processor import (
    ExtractionContext,
    ExtractionError,
    ExtractionResult,
    run_extraction,
)

_JOB_PROCESS_TASK = "jobs.process"
_STATUS_RUNNING = "running"
_STATUS_SUCCEEDED = "succeeded"
_STATUS_FAILED = "failed"


class _JobProcessor:
    """Handle ``jobs.process`` tasks emitted by the queue."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        hub: MessageHub | None,
    ) -> None:
        self._session_factory = session_factory
        self._hub = hub

    async def __call__(self, message: TaskMessage) -> None:
        if message.name != _JOB_PROCESS_TASK:
            return

        job_id = message.payload.get("job_id")
        if not job_id:
            return

        job_id = str(job_id)
        metadata = self._prepare_metadata(message.metadata, job_id)
        correlation_id = message.correlation_id

        session = self._session_factory()
        try:
            job = await session.get(Job, job_id)
            if job is None:
                return

            await self._mark_running(
                session,
                job,
                metadata,
                correlation_id,
            )
            await session.commit()

            context = ExtractionContext(
                job_id=job.job_id,
                document_id=job.input_document_id,
                document_type=job.document_type,
                configuration_id=job.configuration_id,
                configuration_version=job.configuration_version,
            )

            try:
                result = await run_extraction(context)
            except ExtractionError as exc:
                await self._mark_failed(
                    session,
                    job,
                    metadata,
                    correlation_id,
                    error=exc,
                )
                await session.commit()
            except Exception as exc:
                await self._mark_failed(
                    session,
                    job,
                    metadata,
                    correlation_id,
                    error=exc,
                )
                await session.commit()
            else:
                tables = await self._persist_outputs(
                    session,
                    job,
                    result.outputs,
                )
                await self._mark_succeeded(
                    session,
                    job,
                    metadata,
                    correlation_id,
                    result=result,
                    tables=tables,
                )
                await session.commit()
        finally:
            await session.close()

    def _prepare_metadata(
        self, metadata: Mapping[str, Any], job_id: str
    ) -> dict[str, Any]:
        prepared = dict(metadata or {})
        prepared.setdefault("entity_type", "job")
        prepared.setdefault("entity_id", job_id)
        return prepared

    async def _mark_running(
        self,
        session: AsyncSession,
        job: Job,
        metadata: Mapping[str, Any],
        correlation_id: str | None,
    ) -> None:
        await self._clear_outputs(session, job)
        job.status = _STATUS_RUNNING
        job.logs.append(
            {
                "level": "info",
                "message": "Job processing started.",
            }
        )
        await session.flush()
        payload = {"job_id": job.job_id, "status": job.status}
        await self._record_event(
            session,
            name="job.status.running",
            payload=payload,
            metadata=metadata,
            correlation_id=correlation_id,
        )

    async def _mark_succeeded(
        self,
        session: AsyncSession,
        job: Job,
        metadata: Mapping[str, Any],
        correlation_id: str | None,
        *,
        result: ExtractionResult,
        tables: Sequence[ExtractedTable],
    ) -> None:
        job.status = _STATUS_SUCCEEDED
        job.metrics = dict(result.metrics)
        logs = result.as_job_logs()
        if logs:
            job.logs.extend(logs)
        job.logs.append(
            {
                "level": "info",
                "message": "Job processing completed successfully.",
            }
        )
        await session.flush()
        payload = {
            "job_id": job.job_id,
            "status": job.status,
            "metrics": dict(job.metrics),
            "table_count": len(tables),
        }
        await self._record_event(
            session,
            name="job.status.succeeded",
            payload=payload,
            metadata=metadata,
            correlation_id=correlation_id,
        )
        await self._record_outputs_event(
            session,
            job,
            tables,
            metadata,
            correlation_id,
        )

    async def _mark_failed(
        self,
        session: AsyncSession,
        job: Job,
        metadata: Mapping[str, Any],
        correlation_id: str | None,
        *,
        error: Exception,
    ) -> None:
        job.status = _STATUS_FAILED
        job.metrics = {}
        await self._clear_outputs(session, job)
        job.logs.append(
            {
                "level": "error",
                "message": "Job processing failed.",
                "details": {"error": str(error)},
            }
        )
        await session.flush()
        payload = {
            "job_id": job.job_id,
            "status": job.status,
            "error": str(error),
        }
        await self._record_event(
            session,
            name="job.status.failed",
            payload=payload,
            metadata=metadata,
            correlation_id=correlation_id,
        )

    async def _record_event(
        self,
        session: AsyncSession,
        *,
        name: str,
        payload: Mapping[str, Any],
        metadata: Mapping[str, Any],
        correlation_id: str | None,
    ) -> None:
        await persist_event(
            session,
            name=name,
            payload=payload,
            metadata=metadata,
            correlation_id=correlation_id,
        )
        if self._hub is not None:
            await self._hub.publish(
                name,
                payload=payload,
                correlation_id=correlation_id,
                metadata=metadata,
            )

    async def _persist_outputs(
        self,
        session: AsyncSession,
        job: Job,
        outputs: Sequence[Mapping[str, Any]],
    ) -> list[ExtractedTable]:
        repository = ExtractedTablesRepository(session)
        tables = await repository.replace_job_tables(
            job_id=job.job_id,
            document_id=job.input_document_id,
            tables=outputs,
        )
        return tables

    async def _clear_outputs(self, session: AsyncSession, job: Job) -> None:
        repository = ExtractedTablesRepository(session)
        await repository.replace_job_tables(
            job_id=job.job_id,
            document_id=job.input_document_id,
            tables=[],
        )

    async def _record_outputs_event(
        self,
        session: AsyncSession,
        job: Job,
        tables: Sequence[ExtractedTable],
        metadata: Mapping[str, Any],
        correlation_id: str | None,
    ) -> None:
        table_payload = [
            {
                "table_id": table.id,
                "sequence_index": table.sequence_index,
                "row_count": table.row_count,
                "title": table.title,
            }
            for table in tables
        ]
        payload = {
            "job_id": job.job_id,
            "document_id": job.input_document_id,
            "table_count": len(table_payload),
            "tables": table_payload,
        }
        await self._record_event(
            session,
            name="job.outputs.persisted",
            payload=payload,
            metadata=metadata,
            correlation_id=correlation_id,
        )


def register_job_queue_handlers(app: FastAPI) -> None:
    """Attach job-processing subscribers to the application queue."""

    queue: TaskQueue | None = getattr(app.state, "task_queue", None)
    if queue is None:
        return

    hub: MessageHub | None = getattr(app.state, "message_hub", None)
    session_factory = get_sessionmaker()
    processor = _JobProcessor(session_factory=session_factory, hub=hub)
    queue.subscribe(processor)


__all__ = ["register_job_queue_handlers"]
