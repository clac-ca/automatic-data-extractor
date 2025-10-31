"""Job submission and artifact orchestration services."""

import json
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.features.users.models import User
from backend.app.shared.core.config import Settings
from backend.app.shared.core.time import utc_now

from ..configs.repository import ConfigsRepository
from ..configs.models import ConfigVersion
from .exceptions import JobNotFoundError, JobSubmissionError
from .models import Job, JobStatus
from .orchestrator import JobOrchestrator
from .repository import JobsRepository
from .schemas import JobArtifact, JobRecord, JobSubmitRequest
from .storage import JobsStorage


class JobsService:
    """Coordinate job metadata persistence and synchronous execution."""

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._configs = ConfigsRepository(session)
        self._jobs = JobsRepository(session)
        self._storage = JobsStorage(settings)
        self._orchestrator = JobOrchestrator(self._storage)

    async def submit_job(
        self,
        *,
        workspace_id: str,
        request: JobSubmitRequest,
        actor: User | None,
    ) -> JobRecord:
        version = await self._configs.get_version_by_id(request.config_version_id)
        if version is None or version.deleted_at is not None:
            raise JobSubmissionError("Config version is not available")
        if version.config is None or version.config.workspace_id != workspace_id:
            raise JobSubmissionError("Config version does not belong to this workspace")
        if version.config.deleted_at is not None:
            raise JobSubmissionError("Config is archived")

        actor_id = getattr(actor, "id", None)
        job = await self._jobs.create_job(
            workspace_id=workspace_id,
            config_id=version.config_id,
            config_version_id=version.id,
            actor_id=actor_id,
        )

        await self._jobs.update_status(
            job,
            status=JobStatus.RUNNING,
            started_at=utc_now(),
        )

        package_path = Path(version.package_uri)
        if not package_path.exists():
            await self._jobs.update_status(
                job,
                status=JobStatus.FAILED,
                completed_at=utc_now(),
                error_message="Config package directory is missing",
            )
            await self._session.commit()
            raise JobSubmissionError("Config package directory is missing")

        try:
            result = self._orchestrator.run(
                job_id=job.id,
                config_version=version,
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

        await self._jobs.update_status(
            job,
            status=JobStatus.SUCCEEDED,
            completed_at=utc_now(),
            artifact_uri=str(result.artifact_path),
            output_uri=str(result.output_path),
        )
        await self._session.commit()
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


__all__ = ["JobsService"]
