"""Job submission and artifact orchestration services."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.features.users.models import User
from backend.app.shared.core.config import Settings

from ..configs.activation_env import ActivationMetadataStore
from ..configs.repository import ConfigsRepository
from ..configs.models import ConfigVersion
from ..configs.storage import ConfigStorage
from ..documents.repository import DocumentsRepository
from ..documents.storage import DocumentStorage
from .constants import SAFE_MODE_DISABLED_MESSAGE
from .exceptions import JobNotFoundError, JobQueueUnavailableError, JobSubmissionError
from .manager import JobQueueManager, QueueReservation
from .models import Job, JobStatus
from .repository import JobsRepository
from .schemas import JobArtifact, JobRecord, JobSubmitRequest
from .storage import JobsStorage
from .types import ResolvedInput

logger = logging.getLogger(__name__)


class JobsService:
    """Coordinate job metadata persistence and queue interactions."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        queue: JobQueueManager | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._queue = queue
        self._configs = ConfigsRepository(session)
        self._jobs = JobsRepository(session)
        self._storage = JobsStorage(settings)
        self._documents = DocumentsRepository(session)
        self._config_storage = ConfigStorage(settings)
        self._activation_store = ActivationMetadataStore(self._config_storage)
        documents_dir = settings.storage_documents_dir
        if documents_dir is None:
            raise RuntimeError("Document storage directory is not configured")
        self._document_storage = DocumentStorage(documents_dir)

    @property
    def queue_enabled(self) -> bool:
        return self._settings.queue_enabled and self._queue is not None

    def queue_metrics(self) -> dict[str, int] | None:
        if not self.queue_enabled or self._queue is None:
            return None
        return self._queue.metrics()

    async def submit_job(
        self,
        *,
        workspace_id: str,
        request: JobSubmitRequest,
        actor: User | None,
    ) -> JobRecord:
        if self._settings.safe_mode:
            logger.warning(
                "Blocked job submission while ADE_SAFE_MODE is enabled.",
                extra={
                    "workspace_id": workspace_id,
                    "config_version_id": request.config_version_id,
                },
            )
            raise JobSubmissionError(SAFE_MODE_DISABLED_MESSAGE)

        version = await self._configs.get_version_by_id(request.config_version_id)
        if version is None or version.deleted_at is not None:
            raise JobSubmissionError("Config version is not available")
        if version.config is None or version.config.workspace_id != workspace_id:
            raise JobSubmissionError("Config version does not belong to this workspace")
        if version.config.deleted_at is not None:
            raise JobSubmissionError("Config is archived")

        _, computed_hash = await self._resolve_inputs(
            workspace_id=workspace_id,
            request=request,
        )
        input_hash = request.input_hash or computed_hash or uuid4().hex
        trace_id = uuid4().hex

        existing = await self._jobs.find_existing_job(
            workspace_id=workspace_id,
            config_version_id=version.id,
            input_hash=input_hash,
        )
        parent_job_id: str | None = None
        attempt_number = 1
        if existing is not None:
            status = JobStatus(existing.status)
            if status in {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.SUCCEEDED}:
                return self._build_record(existing, version)
            parent_job_id = existing.retry_of_job_id or existing.id
            attempt_number = existing.attempt + 1

        queue = self._queue
        if queue is None:
            raise JobQueueUnavailableError()

        actor_id = getattr(actor, "id", None)
        reservation = await queue.try_reserve()

        try:
            job = await self._jobs.create_job(
                workspace_id=workspace_id,
                config_id=version.config_id,
                config_version_id=version.id,
                actor_id=actor_id,
                input_hash=input_hash,
                trace_id=trace_id,
                document_ids=request.all_document_ids,
                retry_of_job_id=parent_job_id,
                attempt=attempt_number,
            )
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            await reservation.release()
            existing = await self._jobs.find_existing_job(
                workspace_id=workspace_id,
                config_version_id=version.id,
                input_hash=input_hash,
            )
            if existing is None:
                raise
            return self._build_record(existing, version)
        except Exception:
            await self._session.rollback()
            await reservation.release()
            raise

        await self._session.refresh(job)
        try:
            await queue.enqueue(job.id, attempt=job.attempt, reservation=reservation)
        except Exception:
            await reservation.release()
            raise

        return self._build_record(job, version)

    async def retry_job(
        self,
        *,
        workspace_id: str,
        job_id: str,
        actor: User | None,
    ) -> JobRecord:
        job = await self._jobs.get_job(workspace_id=workspace_id, job_id=job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        version = await self._configs.get_version_by_id(job.config_version_id)
        if version is None:
            raise JobNotFoundError(job_id)
        trace_id = uuid4().hex
        next_attempt = job.attempt + 1
        actor_id = getattr(actor, "id", None)

        queue = self._queue
        if queue is None:
            raise JobQueueUnavailableError()

        reservation = await queue.try_reserve()

        try:
            retry_job = await self._jobs.create_job(
                workspace_id=job.workspace_id,
                config_id=job.config_id,
                config_version_id=job.config_version_id,
                actor_id=actor_id,
                input_hash=job.input_hash or uuid4().hex,
                trace_id=trace_id,
                document_ids=list(job.input_documents),
                retry_of_job_id=job.id,
                attempt=next_attempt,
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            await reservation.release()
            raise

        await self._session.refresh(retry_job)
        try:
            await queue.enqueue(retry_job.id, attempt=retry_job.attempt, reservation=reservation)
        except Exception:
            await reservation.release()
            raise

        return self._build_record(retry_job, version)

    async def get_job(
        self,
        *,
        workspace_id: str,
        job_id: str,
    ) -> JobRecord:
        job = await self._jobs.get_job(workspace_id=workspace_id, job_id=job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        version = await self._configs.get_version_by_id(job.config_version_id)
        if version is None:
            raise JobNotFoundError(job_id)
        return self._build_record(job, version)

    async def load_artifact(
        self,
        *,
        workspace_id: str,
        job_id: str,
    ) -> JobArtifact:
        job = await self._jobs.get_job(workspace_id=workspace_id, job_id=job_id)
        if job is None or job.artifact_uri is None:
            raise JobNotFoundError(job_id)
        data = json.loads(Path(job.artifact_uri).read_text(encoding="utf-8"))
        return JobArtifact.model_validate(data)

    async def artifact_path(self, *, workspace_id: str, job_id: str) -> Path:
        job = await self._jobs.get_job(workspace_id=workspace_id, job_id=job_id)
        if job is None or job.artifact_uri is None:
            raise JobNotFoundError(job_id)
        return Path(job.artifact_uri)

    async def output_path(self, *, workspace_id: str, job_id: str) -> Path:
        job = await self._jobs.get_job(workspace_id=workspace_id, job_id=job_id)
        if job is None or job.output_uri is None:
            raise JobNotFoundError(job_id)
        return Path(job.output_uri)

    def _build_record(self, job: Job, version: ConfigVersion) -> JobRecord:
        payload: dict[str, Any] = {
            "job_id": job.id,
            "workspace_id": job.workspace_id,
            "status": JobStatus(job.status),
            "artifact_uri": job.artifact_uri,
            "output_uri": job.output_uri,
            "logs_uri": job.logs_uri,
            "run_request_uri": job.run_request_uri,
            "input_hash": job.input_hash,
            "trace_id": job.trace_id,
            "attempt": job.attempt,
            "queued_at": job.queued_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "last_heartbeat": job.last_heartbeat,
            "error_message": job.error_message,
            "retry_of_job_id": job.retry_of_job_id,
            "config_version": {
                "config_version_id": version.id,
                "config_id": version.config_id,
                "label": version.label,
            },
        }
        activation = self._activation_store.load(config_id=version.config_id, version=version)
        if activation is not None:
            payload["config_version"]["activation"] = {
                "status": activation.status,
                "started_at": activation.started_at,
                "completed_at": activation.completed_at,
                "error": activation.error,
                "venv_path": activation.venv_path.as_posix() if activation.venv_path else None,
                "python_executable": (
                    activation.python_executable.as_posix() if activation.python_executable else None
                ),
                "packages_uri": activation.packages_path.as_posix() if activation.packages_path else None,
                "install_log_uri": activation.install_log_path.as_posix()
                if activation.install_log_path
                else None,
                "hooks_uri": activation.hooks_path.as_posix() if activation.hooks_path else None,
                "diagnostics": activation.diagnostics,
                "annotations": activation.annotations,
            }
        return JobRecord.model_validate(payload)

    async def _resolve_inputs(
        self,
        *,
        workspace_id: str,
        request: JobSubmitRequest,
    ) -> tuple[list[ResolvedInput], str | None]:
        document_ids = request.all_document_ids
        if not document_ids:
            return [], None

        resolved: list[ResolvedInput] = []
        for document_id in document_ids:
            document = await self._documents.get_document(
                workspace_id=workspace_id,
                document_id=document_id,
            )
            if document is None:
                raise JobSubmissionError(f"Document {document_id} is not available")
            try:
                source_path = self._document_storage.path_for(document.stored_uri)
            except ValueError as exc:
                raise JobSubmissionError(
                    f"Document {document_id} has an invalid storage path"
                ) from exc
            if not source_path.exists():
                raise JobSubmissionError(
                    f"Document {document_id} content is missing from storage"
                )
            filename = document.original_filename or f"{document_id}.bin"
            resolved.append(
                ResolvedInput(
                    document_id=document.document_id,
                    source_path=source_path,
                    filename=filename,
                    sha256=document.sha256,
                )
            )

        combined_hash = hashlib.sha256(
            "".join(sorted(item.sha256 for item in resolved)).encode("utf-8")
        ).hexdigest()
        return resolved, combined_hash


__all__ = ["JobsService"]
