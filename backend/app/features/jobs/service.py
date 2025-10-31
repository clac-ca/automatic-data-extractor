"""Service layer orchestrating synchronous job execution."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.shared.core.config import Settings

from ..configs.exceptions import ConfigNotFoundError, ConfigStatusConflictError
from ..configs.files import ConfigFilesystem
from ..configs.models import Config, ConfigStatus
from ..configs.repository import ConfigsRepository
from ..documents.models import Document
from ..documents.storage import DocumentStorage
from .exceptions import (
    ActiveConfigNotFoundError,
    InputDocumentNotFoundError,
    JobExecutionError,
    JobNotFoundError,
)
from .models import Job
from .processor import (
    JobProcessorRequest,
    JobProcessorResult,
    ProcessorError,
    get_job_processor,
)
from .schemas import JobRecord
from .repository import JobsRepository

_VALID_STATUSES = frozenset({"pending", "running", "succeeded", "failed"})


class JobsService:
    """Validate inputs, execute the extractor, and manage job status."""

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        documents_dir = settings.storage_documents_dir
        configs_dir = settings.storage_configs_dir
        if documents_dir is None:
            raise RuntimeError("Document storage directory is not configured")
        if configs_dir is None:
            raise RuntimeError("Configuration storage directory is not configured")

        self._session = session
        self._storage = DocumentStorage(documents_dir)
        self._filesystem = ConfigFilesystem(configs_dir)
        self._configs = ConfigsRepository(session)
        self._jobs = JobsRepository(session)

    async def list_jobs(
        self,
        *,
        workspace_id: str,
        limit: int,
        offset: int,
        status: str | None = None,
        input_document_id: str | None = None,
    ) -> list[JobRecord]:
        """Return recent jobs filtered by optional criteria."""

        if status:
            if status not in _VALID_STATUSES:
                raise ValueError(f"Unsupported job status: {status}")
        jobs = await self._jobs.list_jobs(
            workspace_id=workspace_id,
            limit=limit,
            offset=offset,
            status=status,
            input_document_id=input_document_id,
        )
        records = [JobRecord.model_validate(row) for row in jobs]

        return records

    async def get_job(self, *, workspace_id: str, job_id: str) -> JobRecord:
        """Return a single job by identifier."""

        job = await self._jobs.get_job(workspace_id=workspace_id, job_id=job_id)
        if job is None:
            raise JobNotFoundError(job_id)

        record = JobRecord.model_validate(job)
        return record

    async def submit_job(
        self,
        *,
        workspace_id: str,
        input_document_id: str,
        config_id: str | None = None,
        actor_id: str | None = None,
    ) -> JobRecord:
        """Create a job row, run the processor synchronously, and return the result."""

        document = await self._get_document(workspace_id, input_document_id)
        config = await self._resolve_config(
            workspace_id=workspace_id,
            config_id=config_id,
        )
        run_key = self._compute_run_key(document, config)

        job = Job(
            workspace_id=workspace_id,
            config_id=config.config_id,
            config_files_hash=config.files_hash,
            config_package_sha256=config.package_sha256,
            status="pending",
            created_by_user_id=actor_id,
            input_document_id=document.document_id,
            run_key=run_key,
            metrics={},
            logs=[],
        )
        self._session.add(job)
        await self._session.flush()

        await self._transition_status(job, "running")

        started = perf_counter()
        try:
            result = await self._execute_job(job, document, config, workspace_id=workspace_id)
        except ProcessorError as exc:
            duration_ms = self._duration_ms(started)
            await self._mark_failed(job, str(exc), duration_ms=duration_ms)
            await self._session.flush()
            await self._session.commit()
            raise JobExecutionError(job.job_id, str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive guard
            duration_ms = self._duration_ms(started)
            await self._mark_failed(job, "Job execution failed", duration_ms=duration_ms)
            await self._session.flush()
            await self._session.commit()
            raise JobExecutionError(job.job_id, "Job execution failed") from exc

        duration_ms = self._duration_ms(started)
        await self._finalise_success(job, result, duration_ms)
        await self._session.flush()

        await self._session.refresh(job)
        return JobRecord.model_validate(job)

    async def _execute_job(
        self,
        job: Job,
        document: Document,
        config: Config,
        *,
        workspace_id: str,
    ) -> JobProcessorResult:
        processor = get_job_processor()

        document_path = self._storage.path_for(document.stored_uri)
        manifest = self._load_manifest(config)
        processor_configuration: dict[str, Any] = {
            "manifest": manifest,
            "config_id": config.config_id,
            "files_hash": config.files_hash,
            "package_sha256": config.package_sha256,
            "config_path": str(self._filesystem.config_path(config.config_id)),
        }

        request = JobProcessorRequest(
            job_id=job.job_id,
            document_path=document_path,
            configuration=processor_configuration,
            metadata={
                "document_id": document.document_id,
                "workspace_id": workspace_id,
                "config_id": config.config_id,
            },
        )

        result = await run_in_threadpool(processor, request)
        return result

    async def _get_document(self, workspace_id: str, document_id: str) -> Document:
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

    async def _resolve_config(
        self,
        *,
        workspace_id: str,
        config_id: str | None,
    ) -> Config:
        if config_id:
            config = await self._configs.get_config(
                workspace_id=workspace_id, config_id=config_id
            )
            if config is None:
                raise ConfigNotFoundError(workspace_id, config_id)
        else:
            config = await self._configs.get_active_config(workspace_id)
            if config is None:
                raise ActiveConfigNotFoundError(workspace_id)

        if config.status != ConfigStatus.ACTIVE:
            raise ConfigStatusConflictError(
                config.config_id,
                config.status.value,
                "Configuration must be active to execute jobs",
            )
        return config

    def _load_manifest(self, config: Config) -> dict[str, Any]:
        try:
            payload = self._filesystem.read_text(config.config_id, "manifest.json")
        except FileNotFoundError:
            return {}

        try:
            manifest = json.loads(payload)
        except json.JSONDecodeError:
            return {}

        return manifest

    def _compute_run_key(self, document: Document, config: Config) -> str:
        doc_hash = document.sha256 or ""
        files_hash = config.files_hash or ""
        package_hash = config.package_sha256 or ""
        payload = "|".join([doc_hash, files_hash, package_hash])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

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



__all__ = ["JobsService"]
