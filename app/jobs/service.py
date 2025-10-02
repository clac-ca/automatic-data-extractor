"""Service layer orchestrating synchronous job execution."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.service import BaseService, ServiceContext
from app.models.mixins import generate_ulid
from ..configurations.exceptions import (
    ConfigurationNotFoundError,
    ConfigurationVersionMismatchError,
)
from ..configurations.repository import ConfigurationsRepository
from ..documents.models import Document
from ..documents.storage import DocumentStorage
from ..events.recorder import persist_event
from ..results.repository import ExtractedTablesRepository
from .exceptions import InputDocumentNotFoundError, JobExecutionError, JobNotFoundError
from .models import Job
from .schemas import JobRecord
from .processor import (
    JobProcessorRequest,
    JobProcessorResult,
    ProcessorError,
    get_job_processor,
)

_VALID_STATUSES = frozenset({"pending", "running", "succeeded", "failed"})


class JobsService(BaseService):
    """Validate inputs, execute the extractor, and manage job status."""

    def __init__(self, *, context: ServiceContext) -> None:
        super().__init__(context=context)
        if self.session is None:
            raise RuntimeError("JobsService requires a database session")

        self._session: AsyncSession = self.session
        self._storage = DocumentStorage(self.settings.storage_documents_dir)
        self._configurations = ConfigurationsRepository(self._session)
        self._tables = ExtractedTablesRepository(self._session)

    async def list_jobs(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        input_document_id: str | None = None,
    ) -> list[JobRecord]:
        """Return recent jobs filtered by optional criteria."""

        workspace_id = self.require_workspace_id()

        stmt = self._base_query().order_by(
            Job.created_at.desc(), Job.job_id.desc()
        )
        if status:
            if status not in _VALID_STATUSES:
                raise ValueError(f"Unsupported job status: {status}")
            stmt = stmt.where(Job.status == status)
        if input_document_id:
            stmt = stmt.where(Job.input_document_id == input_document_id)

        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        jobs = result.scalars().all()
        records = [JobRecord.model_validate(row) for row in jobs]

        payload: dict[str, Any] = {
            "count": len(records),
            "limit": limit,
            "offset": offset,
        }
        if status:
            payload["status"] = status
        if input_document_id:
            payload["input_document_id"] = input_document_id

        await self.publish_event(
            "jobs.listed",
            payload,
            metadata={
                "entity_type": "job_collection",
                "entity_id": workspace_id,
            },
        )
        return records

    async def get_job(self, job_id: str) -> JobRecord:
        """Return a single job by identifier."""

        workspace_id = self.require_workspace_id()

        job = await self._session.get(Job, job_id)
        if job is None or job.workspace_id != workspace_id:
            raise JobNotFoundError(job_id)

        record = JobRecord.model_validate(job)
        await self.publish_event(
            "job.viewed",
            {"job_id": record.job_id, "status": record.status},
            metadata={
                "entity_type": "job",
                "entity_id": record.job_id,
                "workspace_id": workspace_id,
            },
        )
        return record

    async def submit_job(
        self,
        *,
        input_document_id: str,
        configuration_id: str,
        configuration_version: int | None = None,
    ) -> JobRecord:
        """Create a job row, run the processor synchronously, and return the result."""

        workspace_id = self.require_workspace_id()

        document = await self._get_document(input_document_id)
        configuration = await self._get_configuration(
            configuration_id, configuration_version
        )
        if configuration.workspace_id != workspace_id:
            raise ConfigurationNotFoundError(configuration_id)
        actor = self._resolve_actor_identifier()
        config_identifier = str(configuration.id)

        job = Job(
            job_id=generate_ulid(),
            workspace_id=workspace_id,
            document_type=configuration.document_type,
            configuration_id=config_identifier,
            configuration_version=configuration.version,
            status="pending",
            created_by=actor,
            input_document_id=document.document_id,
            metrics={},
            logs=[],
        )
        self._session.add(job)
        await self._session.flush()

        metadata = {
            "entity_type": "job",
            "entity_id": job.job_id,
            "workspace_id": workspace_id,
        }
        await self.publish_event(
            "job.submitted",
            {
                "job_id": job.job_id,
                "document_type": job.document_type,
                "configuration_id": config_identifier,
                "configuration_version": job.configuration_version,
            },
            metadata=metadata,
        )

        await self._transition_status(job, "running")
        await self.publish_event(
            "job.running",
            {
                "job_id": job.job_id,
                "document_type": job.document_type,
                "configuration_id": config_identifier,
                "configuration_version": job.configuration_version,
            },
            metadata=metadata,
        )

        started = perf_counter()
        try:
            result = await self._execute_job(job, document, configuration)
        except ProcessorError as exc:
            duration_ms = self._duration_ms(started)
            await self._mark_failed(job, str(exc), duration_ms=duration_ms)
            await self._session.flush()
            await self.publish_event(
                "job.failed",
                {
                    "job_id": job.job_id,
                    "document_type": job.document_type,
                    "configuration_id": config_identifier,
                    "configuration_version": job.configuration_version,
                    "reason": str(exc),
                },
                metadata=metadata,
            )
            await self._session.commit()
            raise JobExecutionError(job.job_id, str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive guard
            duration_ms = self._duration_ms(started)
            await self._mark_failed(job, "Job execution failed", duration_ms=duration_ms)
            await self._session.flush()
            await self.publish_event(
                "job.failed",
                {
                    "job_id": job.job_id,
                    "document_type": job.document_type,
                    "configuration_id": config_identifier,
                    "configuration_version": job.configuration_version,
                    "reason": str(exc),
                },
                metadata=metadata,
            )
            await self._session.commit()
            raise JobExecutionError(job.job_id, "Job execution failed") from exc

        duration_ms = self._duration_ms(started)
        await self._finalise_success(job, result, duration_ms)
        await self._session.flush()
        await self.publish_event(
            "job.succeeded",
            {
                "job_id": job.job_id,
                "document_type": job.document_type,
                "configuration_id": config_identifier,
                "configuration_version": job.configuration_version,
                "metrics": dict(result.metrics),
                "duration_ms": duration_ms,
            },
            metadata=metadata,
        )

        await self._session.refresh(job)
        return JobRecord.model_validate(job)

    async def _execute_job(
        self,
        job: Job,
        document: Document,
        configuration: Any,
    ) -> JobProcessorResult:
        processor = get_job_processor()

        document_path = self._storage.path_for(document.stored_uri)
        config_identifier = str(configuration.id)
        configuration_payload = dict(configuration.payload or {})
        processor_configuration: dict[str, Any] = {
            "configuration_id": config_identifier,
            "version": configuration.version,
            "document_type": configuration.document_type,
        }
        processor_configuration.update(configuration_payload)

        request = JobProcessorRequest(
            job_id=job.job_id,
            document_path=document_path,
            configuration=processor_configuration,
            metadata={
                "document_id": document.document_id,
                "workspace_id": self._collection_entity_id(),
            },
        )

        result = await run_in_threadpool(processor, request)
        await self._tables.replace_job_tables(
            workspace_id=job.workspace_id,
            job_id=job.job_id,
            document_id=document.document_id,
            tables=result.tables,
        )
        return result

    async def _get_document(self, document_id: str) -> Document:
        workspace_id = self.require_workspace_id()
        stmt = (
            select(Document)
            .where(
                Document.id == document_id,
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        document = result.scalar_one_or_none()
        if document is None:
            raise InputDocumentNotFoundError(document_id)
        return document

    async def _get_configuration(
        self, configuration_id: str, version: int | None
    ) -> Any:
        workspace_id = self.require_workspace_id()
        configuration = await self._configurations.get_configuration(
            configuration_id,
            workspace_id=workspace_id,
        )
        if configuration is None:
            raise ConfigurationNotFoundError(configuration_id)
        if version is not None and configuration.version != version:
            raise ConfigurationVersionMismatchError(
                configuration_id,
                expected_version=version,
                actual_version=configuration.version,
            )
        return configuration

    async def _transition_status(self, job: Job, status: str) -> None:
        if status not in _VALID_STATUSES:
            raise ValueError(f"Unsupported job status: {status}")
        job.status = status
        await self._session.flush()

    async def _mark_failed(
        self,
        job: Job,
        reason: str,
        *,
        duration_ms: int,
    ) -> None:
        self._set_job_metrics(job, {"error": reason, "duration_ms": duration_ms})
        self._append_log(job, reason, level="error")
        job.status = "failed"

    async def _finalise_success(
        self,
        job: Job,
        result: JobProcessorResult,
        duration_ms: int,
    ) -> None:
        metrics = dict(result.metrics or {})
        metrics["duration_ms"] = duration_ms
        self._set_job_metrics(job, metrics)
        job.logs = [dict(entry) for entry in result.logs or []]
        job.status = result.status if result.status in _VALID_STATUSES else "succeeded"

    def _set_job_metrics(self, job: Job, metrics: Mapping[str, Any]) -> None:
        job.metrics = {str(key): value for key, value in dict(metrics).items()}

    def _append_log(self, job: Job, message: str, *, level: str = "info") -> None:
        timestamp = datetime.now(tz=UTC).isoformat(timespec="seconds")
        logs = list(job.logs or [])
        logs.append({"ts": timestamp, "level": level, "message": message})
        job.logs = logs

    def _duration_ms(self, started: float) -> int:
        return int((perf_counter() - started) * 1000)

    def _resolve_actor_identifier(self) -> str:
        user = self.current_user
        if user is not None:
            candidate = getattr(user, "id", None) or getattr(user, "email", None)
            if candidate:
                return str(candidate)
        return "system"

    def _collection_entity_id(self) -> str:
        workspace = self.current_workspace
        if workspace is None:
            return "global"
        workspace_id = getattr(workspace, "workspace_id", None) or getattr(
            workspace, "id", None
        )
        if workspace_id is None:
            return "global"
        return str(workspace_id)

    def _base_query(self) -> Select[tuple[Job]]:
        workspace_id = self.require_workspace_id()
        return select(Job).where(Job.workspace_id == workspace_id)

    async def _persist_event(
        self,
        name: str,
        payload: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> None:
        await persist_event(
            self._session,
            name=name,
            payload=payload,
            metadata=metadata,
            correlation_id=self.correlation_id,
        )


__all__ = ["JobsService"]
