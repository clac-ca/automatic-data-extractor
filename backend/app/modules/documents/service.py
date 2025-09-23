"""Service layer for document metadata operations."""

from __future__ import annotations

from ...core.service import BaseService, ServiceContext
from .exceptions import DocumentNotFoundError
from .repository import DocumentsRepository
from .schemas import DocumentRecord


class DocumentsService(BaseService):
    """Expose read-only helpers for document metadata."""

    def __init__(self, *, context: ServiceContext) -> None:
        super().__init__(context=context)
        if self.session is None:
            raise RuntimeError("DocumentsService requires a database session")
        self._repository = DocumentsRepository(self.session)

    async def list_documents(
        self,
        *,
        limit: int,
        offset: int,
        produced_by_job_id: str | None = None,
        include_deleted: bool = False,
    ) -> list[DocumentRecord]:
        """Return documents ordered by recency."""

        documents = await self._repository.list_documents(
            include_deleted=include_deleted,
            produced_by_job_id=produced_by_job_id,
            limit=limit,
            offset=offset,
        )
        records = [DocumentRecord.model_validate(document) for document in documents]

        payload: dict[str, object] = {
            "count": len(records),
            "limit": limit,
            "offset": offset,
        }
        if produced_by_job_id is not None:
            payload["produced_by_job_id"] = produced_by_job_id

        await self.publish_event("documents.listed", payload)
        return records

    async def get_document(
        self, *, document_id: str, include_deleted: bool = False
    ) -> DocumentRecord:
        """Return a single document by identifier."""

        document = await self._repository.get_document(document_id)
        if document is None or (document.deleted_at and not include_deleted):
            raise DocumentNotFoundError(document_id)

        record = DocumentRecord.model_validate(document)
        await self.publish_event(
            "document.viewed",
            {"document_id": record.document_id},
        )
        return record


__all__ = ["DocumentsService"]
