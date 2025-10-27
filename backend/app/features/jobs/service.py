"""Service layer orchestrating synchronous job execution."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.shared.core.config import Settings

from ..configs.exceptions import ConfigVersionNotFoundError
from ..configs.models import Config, ConfigFile, ConfigVersion
from ..documents.models import Document
from ..documents.storage import DocumentStorage
from .exceptions import InputDocumentNotFoundError, JobExecutionError, JobNotFoundError
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
        if documents_dir is None:
            raise RuntimeError("Document storage directory is not configured")

        self._session = session
        self._storage = DocumentStorage(documents_dir)
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
        config_version_id: str,
        actor_id: str | None = None,
    ) -> JobRecord:
        """Create a job row, run the processor synchronously, and return the result."""

        document = await self._get_document(workspace_id, input_document_id)
        config_version = await self._get_config_version(
            workspace_id=workspace_id,
            config_version_id=config_version_id,
        )
        run_key = self._compute_run_key(document, config_version)

        job = Job(
            workspace_id=workspace_id,
            config_version_id=str(config_version.id),
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
            result = await self._execute_job(
                job, document, config_version, workspace_id=workspace_id
            )
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
        config_version: ConfigVersion,
        *,
        workspace_id: str,
    ) -> JobProcessorResult:
        processor = get_job_processor()

        document_path = self._storage.path_for(document.stored_uri)
        manifest = self._load_manifest(config_version)
        processor_configuration: dict[str, Any] = dict(manifest)
        processor_configuration.setdefault("config_version_id", str(config_version.id))
        processor_configuration["files_hash"] = config_version.files_hash
        processor_configuration["files"] = self._files_map(config_version.files or [])

        request = JobProcessorRequest(
            job_id=job.job_id,
            document_path=document_path,
            configuration=processor_configuration,
            metadata={
                "document_id": document.document_id,
                "workspace_id": workspace_id,
                "config_id": config_version.config_id,
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

    async def _get_config_version(
        self,
        *,
        workspace_id: str,
        config_version_id: str,
    ) -> ConfigVersion:
        stmt = (
            select(ConfigVersion)
            .join(Config, Config.id == ConfigVersion.config_id)
            .options(selectinload(ConfigVersion.files))
            .where(
                ConfigVersion.id == config_version_id,
                Config.workspace_id == workspace_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        version = result.scalar_one_or_none()
        if version is None or version.status != "published":
            raise ConfigVersionNotFoundError(config_version_id)
        return version

    def _load_manifest(self, config_version: ConfigVersion) -> dict[str, Any]:
        raw = config_version.manifest_json or "{}"
        try:
            manifest = json.loads(raw)
        except json.JSONDecodeError:
            manifest = {}
        manifest.setdefault("files_hash", config_version.files_hash)
        return manifest

    def _files_map(self, files: Sequence[ConfigFile]) -> dict[str, str]:
        return {file.path: file.code for file in files}

    def _compute_run_key(self, document: Document, config_version: ConfigVersion) -> str:
        doc_hash = document.sha256 or ""
        files_hash = config_version.files_hash or ""
        flags = ""
        resource_versions = ""
        payload = "|".join([doc_hash, files_hash, flags, resource_versions])
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
