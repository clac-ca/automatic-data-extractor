from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...core.service import BaseService, ServiceContext
from ..documents.exceptions import DocumentNotFoundError
from ..documents.models import Document
from ..events.recorder import persist_event
from ..jobs.exceptions import JobNotFoundError
from ..jobs.models import Job
from .exceptions import ExtractedTableNotFoundError, JobResultsUnavailableError
from .repository import ExtractedTablesRepository
from .schemas import ExtractedTableRecord


class ExtractionResultsService(BaseService):
    """Expose helpers for reading extracted table artefacts."""

    def __init__(self, *, context: ServiceContext) -> None:
        super().__init__(context=context)
        if self.session is None:
            raise RuntimeError("ExtractionResultsService requires a database session")
        self._repository = ExtractedTablesRepository(self.session)

    async def list_tables_for_job(self, *, job_id: str) -> list[ExtractedTableRecord]:
        """Return extracted tables associated with ``job_id``."""

        job = await self._get_job(job_id)
        tables = await self._repository.list_for_job(job.job_id)
        records = [ExtractedTableRecord.model_validate(table) for table in tables]

        metadata = {"entity_type": "job", "entity_id": job.job_id}
        payload = {
            "job_id": job.job_id,
            "document_id": job.input_document_id,
            "table_count": len(records),
            "job_status": job.status,
        }
        await self.publish_event("job.outputs.viewed", payload, metadata=metadata)
        return records

    async def list_tables_for_document(
        self, *, document_id: str
    ) -> list[ExtractedTableRecord]:
        """Return extracted tables associated with ``document_id``."""

        await self._ensure_document_exists(document_id)
        tables = await self._repository.list_for_document(document_id)
        records = [ExtractedTableRecord.model_validate(table) for table in tables]

        metadata = {"entity_type": "document", "entity_id": document_id}
        payload = {"document_id": document_id, "table_count": len(records)}
        await self.publish_event("document.outputs.viewed", payload, metadata=metadata)
        return records

    async def get_table(
        self, *, job_id: str, table_id: str
    ) -> ExtractedTableRecord:
        """Return a single table associated with ``job_id``."""

        job = await self._get_job(job_id)
        table = await self._repository.get_table(table_id)
        if table is None or table.job_id != job.job_id:
            raise ExtractedTableNotFoundError(table_id)

        record = ExtractedTableRecord.model_validate(table)
        metadata = {"entity_type": "table", "entity_id": record.table_id}
        payload = {
            "table_id": record.table_id,
            "job_id": record.job_id,
            "document_id": record.document_id,
            "job_status": job.status,
        }
        await self.publish_event("table.viewed", payload, metadata=metadata)
        return record

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

    async def _get_job(self, job_id: str) -> Job:
        if self.session is None:
            raise RuntimeError("ExtractionResultsService requires a database session")

        job = await self.session.get(Job, job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        if job.status != "succeeded":
            raise JobResultsUnavailableError(job.job_id, job.status)
        return job

    async def _ensure_document_exists(self, document_id: str) -> None:
        if self.session is None:
            raise RuntimeError("ExtractionResultsService requires a database session")

        document = await self.session.get(Document, document_id)
        if document is None or document.deleted_at is not None:
            raise DocumentNotFoundError(document_id)


__all__ = ["ExtractionResultsService"]
