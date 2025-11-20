"""Job orchestration service coordinating storage and run execution."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.features.configs.models import Configuration
from ade_api.features.configs.repository import ConfigurationsRepository
from ade_api.features.documents.models import Document
from ade_api.features.documents.repository import DocumentsRepository
from ade_api.features.documents.storage import DocumentStorage
from ade_api.features.documents.staging import stage_document_input
from ade_api.features.jobs.models import Job, JobStatus
from ade_api.features.jobs.repository import JobsRepository
from ade_api.features.jobs.schemas import (
    JobConfigVersion,
    JobInputDocument,
    JobRecord,
    JobSubmissionRequest,
    JobSubmittedBy,
)
from ade_api.features.runs.models import RunStatus
from ade_api.features.runs.schemas import (
    RunCompletedEvent,
    RunCreateOptions,
    RunEvent,
    RunStartedEvent,
)
from ade_api.features.runs.service import RunExecutionContext, RunsService
from ade_api.features.users.models import User
from ade_api.settings import Settings
from ade_api.shared.core.ids import generate_ulid
from ade_api.shared.core.time import utc_now
from ade_api.shared.db.session import get_sessionmaker

if TYPE_CHECKING:  # pragma: no cover - import guard for optional dependency
    from fastapi import BackgroundTasks


logger = logging.getLogger(__name__)


class JobSubmissionError(RuntimeError):
    """Base error raised during job submission."""


class JobDocumentMissingError(JobSubmissionError):
    """Raised when the referenced document cannot be located."""


class JobConfigurationMissingError(JobSubmissionError):
    """Raised when the referenced configuration cannot be found."""


class JobNotFoundError(JobSubmissionError):
    """Raised when a requested job cannot be located."""


class JobArtifactMissingError(JobSubmissionError):
    """Raised when a requested job artifact is unavailable."""


class JobLogsMissingError(JobSubmissionError):
    """Raised when a requested job log stream is unavailable."""


class JobOutputMissingError(JobSubmissionError):
    """Raised when a requested job output path cannot be read."""


class JobsService:
    """Coordinate workspace job submissions and historical lookups."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        runs_service: RunsService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._jobs = JobsRepository(session)
        self._documents = DocumentsRepository(session)
        self._configs = ConfigurationsRepository(session)
        self._runs = runs_service or RunsService(session=session, settings=settings)

        if settings.documents_dir is None:
            raise RuntimeError("ADE_DOCUMENTS_DIR is not configured")
        if settings.jobs_dir is None:
            raise RuntimeError("ADE_JOBS_DIR is not configured")
        self._documents_dir = settings.documents_dir
        self._jobs_dir = settings.jobs_dir
        self._storage = DocumentStorage(self._documents_dir)

    async def submit_job(
        self,
        *,
        workspace_id: str,
        payload: JobSubmissionRequest,
        actor: User | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> JobRecord:
        """Create a job, enqueue execution, and return the resulting record."""

        document = await self._require_document(
            workspace_id=workspace_id,
            document_id=payload.input_document_id,
        )
        configuration = await self._require_configuration(
            workspace_id=workspace_id,
            config_version_id=payload.config_version_id,
        )

        job_id = generate_ulid()
        run, context = await self._runs.prepare_run(
            config_id=configuration.config_id,
            options=payload.options,
            job_id=job_id,
            jobs_dir=self._jobs_dir,
        )
        context = self._ensure_job_context(context, run.id, workspace_id)

        job_dir = self._runs.job_directory(context.job_id or context.run_id)
        await stage_document_input(
            document=document,
            storage=self._storage,
            session=self._session,
            job_dir=job_dir,
        )

        now = utc_now()
        job = Job(
            id=job_id,
            workspace_id=workspace_id,
            config_id=configuration.config_id,
            config_version_id=payload.config_version_id,
            submitted_by_user_id=getattr(actor, "id", None),
            status=JobStatus.QUEUED,
            queued_at=now,
            input_documents=[self._document_descriptor(document)],
            trace_id=run.id,
            run_request_uri=f"/api/v1/runs/{run.id}",
        )
        self._session.add(job)
        await self._session.flush()

        document.last_run_at = now
        await self._session.flush()

        await self._session.refresh(job)
        await self._session.commit()

        context_dict = context.as_dict()
        options_dict = payload.options.model_dump()

        if background_tasks is None:
            await self.execute_job(
                job_id=job.id,
                context=context,
                options=payload.options,
            )
            await self._session.refresh(job)
            return self._to_record(job, configuration)

        background_tasks.add_task(
            _execute_job_background,
            job.id,
            context_dict,
            options_dict,
            self._settings,
        )
        return self._to_record(job, configuration)

    async def list_jobs(
        self,
        *,
        workspace_id: str,
        status: JobStatus | None = None,
        input_document_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[JobRecord]:
        """Return job records for ``workspace_id``."""

        jobs = await self._jobs.list_jobs(
            workspace_id=workspace_id,
            status=status,
            input_document_id=input_document_id,
            limit=limit,
            offset=offset,
        )
        config_map = await self._configuration_map(workspace_id, [job.config_id for job in jobs])
        return [self._to_record(job, config_map.get(job.config_id)) for job in jobs]

    async def get_job(self, *, workspace_id: str, job_id: str) -> JobRecord | None:
        """Return a single job record when available."""

        job = await self._jobs.get_job(workspace_id=workspace_id, job_id=job_id)
        if job is None:
            return None
        configuration = await self._configs.get(
            workspace_id=workspace_id,
            config_id=job.config_id,
        )
        return self._to_record(job, configuration)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _require_document(self, *, workspace_id: str, document_id: str) -> Document:
        document = await self._documents.get_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
        if document is None:
            raise JobDocumentMissingError(f"Document {document_id} not found")
        return document

    async def _require_configuration(
        self,
        *,
        workspace_id: str,
        config_version_id: str,
    ) -> Configuration:
        configuration = await self._configs.get(
            workspace_id=workspace_id,
            config_id=config_version_id,
        )
        if configuration is None:
            raise JobConfigurationMissingError(
                f"Configuration {config_version_id} not found"
            )
        return configuration

    def _document_descriptor(self, document: Document) -> dict[str, object]:
        return {
            "document_id": document.id,
            "display_name": document.original_filename,
            "name": document.original_filename,
            "original_filename": document.original_filename,
            "content_type": document.content_type,
            "byte_size": document.byte_size,
        }

    async def _finalize_job(
        self,
        job: Job,
        configuration: Configuration | None,
        job_dir: Path,
    ) -> None:
        run = await self._runs.get_run(job.trace_id or "")
        if run is None:
            job.status = JobStatus.FAILED
            job.error_message = (
                job.error_message
                or "Run record not found; job status could not be reconciled."
            )
            job.completed_at = job.completed_at or utc_now()
        else:
            job.error_message = run.error_message
            job.started_at = run.started_at or job.started_at or utc_now()
            job.completed_at = run.finished_at or job.completed_at or utc_now()
            status_map = {
                RunStatus.SUCCEEDED: JobStatus.SUCCEEDED,
                RunStatus.FAILED: JobStatus.FAILED,
                RunStatus.CANCELED: JobStatus.CANCELLED,
                RunStatus.RUNNING: JobStatus.RUNNING,
                RunStatus.QUEUED: JobStatus.QUEUED,
            }
            job.status = status_map.get(run.status, JobStatus.FAILED)

        job.artifact_uri = self._runs.job_relative_path(job_dir / "logs" / "artifact.json")
        job.logs_uri = self._runs.job_relative_path(job_dir / "logs" / "events.ndjson")
        job.output_uri = self._runs.job_relative_path(job_dir / "output")

    async def _mark_job_failure(self, job: Job, message: str) -> None:
        job.status = JobStatus.FAILED
        job.error_message = message
        job.completed_at = utc_now()
        await self._session.flush()

    async def _apply_run_frame(self, job: Job, frame: object) -> None:
        if not isinstance(frame, RunEvent):
            return

        if isinstance(frame, RunStartedEvent):
            job.status = JobStatus.RUNNING
            job.started_at = job.started_at or self._epoch_to_datetime(frame.created)
            await self._session.flush()
            return

        if isinstance(frame, RunCompletedEvent):
            run_status = RunStatus(frame.status)
            status_map = {
                RunStatus.SUCCEEDED: JobStatus.SUCCEEDED,
                RunStatus.FAILED: JobStatus.FAILED,
                RunStatus.CANCELED: JobStatus.CANCELLED,
                RunStatus.RUNNING: JobStatus.RUNNING,
                RunStatus.QUEUED: JobStatus.QUEUED,
            }
            job.status = status_map.get(run_status, JobStatus.FAILED)
            job.error_message = frame.error_message
            job.started_at = job.started_at or self._epoch_to_datetime(frame.created)
            job.completed_at = job.completed_at or self._epoch_to_datetime(frame.created)
            await self._session.flush()

    @staticmethod
    def _epoch_to_datetime(epoch_seconds: int) -> datetime:
        return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)

    async def _require_job(self, *, workspace_id: str, job_id: str) -> Job:
        job = await self._jobs.get_job(workspace_id=workspace_id, job_id=job_id)
        if job is None:
            job = await self._session.get(Job, job_id)
        if job is None:
            raise JobNotFoundError(f"Job {job_id} not found")
        return job

    async def execute_job(
        self,
        *,
        job_id: str,
        context: RunExecutionContext,
        options: RunCreateOptions,
    ) -> None:
        job = await self._jobs.get_job(
            workspace_id=context.workspace_id,
            job_id=job_id,
        )
        if job is None:
            return

        configuration = await self._configs.get(
            workspace_id=context.workspace_id,
            config_id=context.config_id,
        )

        job_dir = self._runs.job_directory(context.job_id or context.run_id)
        job_dir.mkdir(parents=True, exist_ok=True)

        try:
            async for frame in self._runs.stream_run(context=context, options=options):
                await self._apply_run_frame(job, frame)
        except Exception as exc:  # pragma: no cover - defensive
            await self._mark_job_failure(job, str(exc))
            await self._session.commit()
            raise

        await self._finalize_job(job, configuration, job_dir)
        await self._session.commit()

    async def get_artifact_path(self, *, workspace_id: str, job_id: str) -> Path:
        job = await self._require_job(workspace_id=workspace_id, job_id=job_id)
        if not job.artifact_uri:
            raise JobArtifactMissingError("Job artifact is unavailable")

        path = self._job_path(job.artifact_uri)
        if not path.is_file():
            raise JobArtifactMissingError("Job artifact file not found")
        return path

    async def get_logs_path(self, *, workspace_id: str, job_id: str) -> Path:
        job = await self._require_job(workspace_id=workspace_id, job_id=job_id)
        if not job.logs_uri:
            raise JobLogsMissingError("Job logs are unavailable")

        path = self._job_path(job.logs_uri)
        if not path.is_file():
            raise JobLogsMissingError("Job logs file not found")
        return path

    async def list_output_files(
        self,
        *,
        workspace_id: str,
        job_id: str,
    ) -> list[tuple[str, int]]:
        job = await self._require_job(workspace_id=workspace_id, job_id=job_id)
        if not job.output_uri:
            raise JobOutputMissingError("Job output is unavailable")

        output_dir = self._job_path(job.output_uri)
        if not output_dir.exists():
            raise JobOutputMissingError("Job output directory not found")

        files: list[tuple[str, int]] = []
        for path in output_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                relative = path.relative_to(output_dir)
            except ValueError:
                continue
            size = path.stat().st_size
            files.append((str(relative), size))
        return files

    async def resolve_output_file(
        self,
        *,
        workspace_id: str,
        job_id: str,
        relative_path: str,
    ) -> Path:
        job = await self._require_job(workspace_id=workspace_id, job_id=job_id)
        if not job.output_uri:
            raise JobOutputMissingError("Job output is unavailable")

        output_dir = self._job_path(job.output_uri)
        candidate = (output_dir / relative_path).resolve()
        try:
            candidate.relative_to(output_dir)
        except ValueError:
            raise JobOutputMissingError("Requested output is outside the job directory")

        if not candidate.is_file():
            raise JobOutputMissingError("Requested output file not found")

        return candidate

    def _job_path(self, uri: str) -> Path:
        root = self._jobs_dir.resolve()
        candidate = (self._jobs_dir / uri).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            raise JobOutputMissingError("Requested path escapes jobs directory")
        return candidate

    async def _configuration_map(
        self,
        workspace_id: str,
        config_ids: Iterable[str],
    ) -> dict[str, Configuration]:
        unique_ids = list(dict.fromkeys(config_ids))
        if not unique_ids:
            return {}
        records = await self._configs.list_for_workspace(workspace_id)
        return {record.config_id: record for record in records if record.config_id in unique_ids}

    def _ensure_job_context(
        self,
        context: RunExecutionContext,
        job_id: str,
        workspace_id: str,
    ) -> RunExecutionContext:
        if (
            context.job_id == job_id
            and context.jobs_dir
            and context.workspace_id == workspace_id
        ):
            return context
        return replace(
            context,
            job_id=job_id,
            jobs_dir=str(self._jobs_dir),
            workspace_id=workspace_id,
        )

    def _to_record(
        self,
        job: Job,
        configuration: Configuration | None,
    ) -> JobRecord:
        submitted = (
            JobSubmittedBy(
                id=job.submitted_by_user.id,
                display_name=job.submitted_by_user.display_name,
                email=job.submitted_by_user.email,
            )
            if job.submitted_by_user is not None
            else None
        )

        documents = [JobInputDocument.model_validate(doc) for doc in job.input_documents or []]
        config_version = JobConfigVersion(config_version_id=job.config_version_id)
        config_title = configuration.display_name if configuration is not None else None

        return JobRecord(
            id=job.id,
            workspace_id=job.workspace_id,
            config_id=job.config_id,
            config_version_id=job.config_version_id,
            status=job.status.value,  # type: ignore[arg-type]
            queued_at=job.queued_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            cancelled_at=job.cancelled_at,
            updated_at=job.updated_at,
            input_documents=documents,
            config_title=config_title,
            config_version=config_version,
            submitted_by_user=submitted,
            submitted_by=submitted.display_name if submitted else None,
            error_message=job.error_message,
            artifact_uri=job.artifact_uri,
            logs_uri=job.logs_uri,
            output_uri=job.output_uri,
        )


async def _execute_job_background(
    job_id: str,
    context_data: dict[str, str],
    options_data: dict[str, object],
    settings: Settings,
) -> None:
    """Execute a job using a fresh session for background tasks."""

    session_factory = get_sessionmaker(settings=settings)
    context = RunExecutionContext.from_dict(context_data)
    options = RunCreateOptions(**options_data)

    async with session_factory() as session:
        service = JobsService(session=session, settings=settings)
        try:
            await service.execute_job(job_id=job_id, context=context, options=options)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Background job execution failed", extra={"job_id": job_id})


__all__ = [
    "JobsService",
    "JobDocumentMissingError",
    "JobConfigurationMissingError",
    "JobNotFoundError",
    "JobArtifactMissingError",
    "JobLogsMissingError",
    "JobOutputMissingError",
]
