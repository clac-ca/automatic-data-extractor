"""Job submission and artifact orchestration services."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Iterable, Sequence
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.features.users.models import User
from backend.app.features.configs.spec import ManifestLoader, ManifestV1
from backend.app.shared.core.config import Settings
from backend.app.shared.core.time import utc_now

from ..configs.repository import ConfigsRepository
from ..configs.models import ConfigVersion
from ..documents.repository import DocumentsRepository
from ..documents.storage import DocumentStorage
from .exceptions import JobNotFoundError, JobSubmissionError
from .models import Job, JobStatus
from .orchestrator import JobOrchestrator
from .repository import JobsRepository
from .schemas import JobArtifact, JobRecord, JobSubmitRequest
from .storage import JobsStorage
from .types import ResolvedInput

SAFE_MODE_DISABLED_MESSAGE = (
    "ADE_SAFE_MODE is enabled. Job execution is temporarily disabled so you can revert config changes and restart without safe mode."
)
logger = logging.getLogger(__name__)


class JobsService:
    """Coordinate job metadata persistence and synchronous execution."""

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._configs = ConfigsRepository(session)
        self._jobs = JobsRepository(session)
        self._storage = JobsStorage(settings)
        self._orchestrator = JobOrchestrator(
            self._storage,
            settings=settings,
            safe_mode_message=SAFE_MODE_DISABLED_MESSAGE,
        )
        self._manifest_loader = ManifestLoader()
        self._documents = DocumentsRepository(session)
        documents_dir = settings.storage_documents_dir
        if documents_dir is None:
            raise RuntimeError("Document storage directory is not configured")
        self._document_storage = DocumentStorage(documents_dir)

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

        manifest = self._load_manifest(version)
        inputs, computed_hash = await self._resolve_inputs(
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

        if existing is not None:
            status = JobStatus(existing.status)
            if status in {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.SUCCEEDED}:
                return self._build_record(existing, version)
            job = await self._jobs.reset_for_retry(existing, trace_id=trace_id)
        else:
            actor_id = getattr(actor, "id", None)
            job = await self._jobs.create_job(
                workspace_id=workspace_id,
                config_id=version.config_id,
                config_version_id=version.id,
                actor_id=actor_id,
                input_hash=input_hash,
                trace_id=trace_id,
            )

        actor_id = getattr(actor, "id", None)
        await self._jobs.update_status(
            job,
            status=JobStatus.RUNNING,
            started_at=utc_now(),
        )

        package_path = Path(version.package_path)
        if not package_path.exists():
            await self._jobs.update_status(
                job,
                status=JobStatus.FAILED,
                completed_at=utc_now(),
                error_message="Config package directory is missing",
            )
            await self._session.commit()
            raise JobSubmissionError("Config package directory is missing")

        paths = None
        try:
            run_result, paths = await self._orchestrator.run(
                job_id=job.id,
                config_version=version,
                manifest=manifest,
                trace_id=trace_id,
                input_files=inputs,
                timeout_seconds=max(1.0, manifest.engine.defaults.timeout_ms / 1000),
            )
        except Exception as exc:  # pragma: no cover - defensive failure path
            await self._jobs.update_status(
                job,
                status=JobStatus.FAILED,
                completed_at=utc_now(),
                error_message=str(exc),
            )
            await self._session.commit()
            raise JobSubmissionError("Job execution failed") from exc
        finally:
            if paths is not None:
                self._storage.cleanup_inputs(paths)

        await self._jobs.record_paths(
            job,
            logs_uri=str(paths.logs_path),
            run_request_uri=str(paths.request_path),
        )

        if run_result.status == "succeeded" and run_result.artifact_path and run_result.output_path:
            await self._jobs.update_status(
                job,
                status=JobStatus.SUCCEEDED,
                completed_at=utc_now(),
                artifact_uri=str(run_result.artifact_path),
                output_uri=str(run_result.output_path),
            )
        else:
            error_message = run_result.error_message or self._summarise_diagnostics(run_result.diagnostics)
            if run_result.timed_out:
                error_message = error_message or "Worker timed out"
            await self._jobs.update_status(
                job,
                status=JobStatus.FAILED,
                completed_at=utc_now(),
                error_message=error_message,
            )
        await self._session.commit()
        await self._session.refresh(job)
        return self._build_record(job, version)

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
            "error_message": job.error_message,
            "config_version": {
                "config_version_id": version.id,
                "config_id": version.config_id,
                "label": version.label,
            },
        }
        return JobRecord.model_validate(payload)

    def _summarise_diagnostics(self, diagnostics: list[dict[str, Any]]) -> str | None:
        if not diagnostics:
            return None
        first = diagnostics[0]
        message = first.get("message")
        code = first.get("code")
        if message and code:
            return f"{code}: {message}"
        return message or code

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
                raise JobSubmissionError(f"Document {document_id} has an invalid storage path") from exc
            if not source_path.exists():
                raise JobSubmissionError(f"Document {document_id} content is missing from storage")
            filename = document.original_filename or f"{document_id}.bin"
            resolved.append(
                ResolvedInput(
                    document_id=document.document_id,
                    source_path=source_path,
                    filename=filename,
                    sha256=document.sha256,
                )
            )

        combined_hash = hashlib.sha256("".join(sorted(item.sha256 for item in resolved)).encode("utf-8")).hexdigest()
        return resolved, combined_hash

    def _load_manifest(self, version: ConfigVersion) -> ManifestV1:
        try:
            return self._manifest_loader.load(version.manifest)
        except Exception as exc:  # pragma: no cover - manifests validated on publish
            raise JobSubmissionError("Stored manifest is invalid") from exc


__all__ = ["JobsService", "SAFE_MODE_DISABLED_MESSAGE"]
