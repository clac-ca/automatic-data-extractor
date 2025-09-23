"""Persistence helpers for document metadata."""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Document


class DocumentsRepository:
    """Query helper responsible for document lookups."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_documents(
        self,
        *,
        include_deleted: bool = False,
        produced_by_job_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Document]:
        """Return documents ordered by recency."""

        stmt: Select[tuple[Document]] = select(Document).order_by(
            Document.created_at.desc(),
            Document.id.desc(),
        )
        if not include_deleted:
            stmt = stmt.where(Document.deleted_at.is_(None))
        if produced_by_job_id is not None:
            stmt = stmt.where(Document.produced_by_job_id == produced_by_job_id)
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_document(self, document_id: str) -> Document | None:
        """Return the document identified by ``document_id`` when available."""

        return await self._session.get(Document, document_id)


__all__ = ["DocumentsRepository"]
