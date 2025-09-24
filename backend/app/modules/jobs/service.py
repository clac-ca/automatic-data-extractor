"""Service layer for job orchestration operations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...core.service import BaseService, ServiceContext
from ...db.mixins import generate_ulid
from ..configurations.exceptions import (
    ActiveConfigurationNotFoundError,
    ConfigurationMismatchError,
    ConfigurationNotFoundError,
    ConfigurationVersionMismatchError,
    ConfigurationVersionNotFoundError,
)
from ..configurations.models import Configuration
from ..configurations.repository import ConfigurationsRepository
from ..documents.models import Document
from ..events.recorder import persist_event
from .exceptions import InputDocumentNotFoundError, JobNotFoundError
from .models import Job
from .repository import JobsRepository
from .schemas import JobRecord


class JobsService(BaseService):
    """Expose helpers for job metadata and orchestration."""

    def __init__(self, *, context: ServiceContext) -> None:
        super().__init__(context=context)
        if self.session is None:
            raise RuntimeError("JobsService requires a database session")
        self._repository = JobsRepository(self.session)
        self._config_repository = ConfigurationsRepository(self.session)

    async def create_job(
        self,
        *,
        input_document_id: str,
        document_type: str,
        configuration_id: str | None = None,
        configuration_version: int | None = None,
    ) -> JobRecord:
        """Persist a new job record and enqueue it for processing."""

        if self.session is None:
            raise RuntimeError("JobsService requires a database session")

        document = await self._ensure_document(input_document_id)
        configuration = await self._resolve_configuration(
            document_type=document_type,
            configuration_id=configuration_id,
            configuration_version=configuration_version,
        )

        job_id = generate_ulid()
        created_by = self._resolve_created_by()
        job = await self._repository.create_job(
            job_id=job_id,
            document_type=document_type,
            configuration_id=str(configuration.id),
            configuration_version=configuration.version,
            status="pending",
            created_by=created_by,
            input_document_id=str(document.id),
        )

        metadata = {"entity_type": "job", "entity_id": job_id}
        payload = self._build_job_created_payload(job)

        session = self.session
        try:
            await self.publish_event("job.created", payload, metadata=metadata)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        await self._enqueue_job(job)
        await session.refresh(job)
        return JobRecord.model_validate(job)

    async def list_jobs(
        self,
        *,
        limit: int,
        offset: int,
        input_document_id: str | None = None,
    ) -> list[JobRecord]:
        """Return jobs ordered by recency."""

        jobs = await self._repository.list_jobs(
            input_document_id=input_document_id,
            limit=limit,
            offset=offset,
        )
        records = [JobRecord.model_validate(job) for job in jobs]

        payload: dict[str, Any] = {
            "count": len(records),
            "limit": limit,
            "offset": offset,
        }
        if input_document_id is not None:
            payload["input_document_id"] = input_document_id

        metadata: dict[str, Any] = {"entity_type": "job_collection"}
        workspace = self.current_workspace
        workspace_id = None
        if workspace is not None:
            workspace_id = getattr(workspace, "workspace_id", None) or getattr(
                workspace, "id", None
            )
        metadata["entity_id"] = str(workspace_id) if workspace_id is not None else "global"

        await self.publish_event("jobs.listed", payload, metadata=metadata)
        return records

    async def get_job(
        self,
        *,
        job_id: str,
        emit_event: bool = True,
    ) -> JobRecord:
        """Return a single job by identifier."""

        job = await self._repository.get_job(job_id)
        if job is None:
            raise JobNotFoundError(job_id)

        record = JobRecord.model_validate(job)
        if emit_event:
            metadata = {"entity_type": "job", "entity_id": record.job_id}
            payload = {"job_id": record.job_id, "status": record.status}
            await self.publish_event(
                "job.viewed",
                payload,
                metadata=metadata,
            )
        return record

    async def _ensure_document(self, document_id: str) -> Document:
        if self.session is None:
            raise RuntimeError("JobsService requires a database session")

        document = await self.session.get(Document, document_id)
        if document is None or document.deleted_at is not None:
            raise InputDocumentNotFoundError(document_id)
        return document

    async def _resolve_configuration(
        self,
        *,
        document_type: str,
        configuration_id: str | None,
        configuration_version: int | None,
    ) -> Configuration:
        repository = self._config_repository

        if configuration_id is not None:
            configuration = await repository.get_configuration(configuration_id)
            if configuration is None:
                raise ConfigurationNotFoundError(configuration_id)
            if configuration.document_type != document_type:
                raise ConfigurationMismatchError(
                    configuration_id,
                    expected_document_type=document_type,
                    actual_document_type=configuration.document_type,
                )
            if (
                configuration_version is not None
                and configuration.version != configuration_version
            ):
                raise ConfigurationVersionMismatchError(
                    configuration_id,
                    expected_version=configuration_version,
                    actual_version=configuration.version,
                )
            return configuration

        if configuration_version is not None:
            configuration = await repository.get_configuration_by_version(
                document_type=document_type,
                version=configuration_version,
            )
            if configuration is None:
                raise ConfigurationVersionNotFoundError(
                    document_type, configuration_version
                )
            return configuration

        configuration = await repository.get_active_configuration(document_type)
        if configuration is None:
            raise ActiveConfigurationNotFoundError(document_type)
        return configuration

    def _resolve_created_by(self) -> str:
        user = self.current_user
        if user is not None:
            email = getattr(user, "email", None)
            if email:
                return str(email)

        service_account = self.current_service_account
        if service_account is not None:
            label = getattr(service_account, "display_name", None) or getattr(
                service_account, "name", None
            )
            if label:
                return str(label)

        return "system"

    def _build_job_created_payload(self, job: Job) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "document_type": job.document_type,
            "configuration_id": job.configuration_id,
            "configuration_version": job.configuration_version,
            "status": job.status,
            "created_by": job.created_by,
            "input_document_id": job.input_document_id,
        }

    async def _enqueue_job(self, job: Job) -> None:
        queue = self.task_queue
        if queue is None:
            return

        metadata = self._build_event_metadata(
            {"entity_type": "job", "entity_id": job.job_id}
        )
        payload = {
            "job_id": job.job_id,
            "document_type": job.document_type,
            "configuration_id": job.configuration_id,
        }
        await queue.enqueue(
            "jobs.process",
            payload,
            correlation_id=self.correlation_id,
            metadata=metadata,
        )

    async def _persist_event(
        self,
        name: str,
        payload: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> None:
        if self.session is None:
            return

        await persist_event(
            self.session,
            name=name,
            payload=payload,
            metadata=metadata,
            correlation_id=self.correlation_id,
        )


__all__ = ["JobsService"]
