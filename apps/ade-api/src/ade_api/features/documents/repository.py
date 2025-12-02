"""Data access helpers for document records."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ade_api.core.models import Document


class DocumentsRepository:
    """Encapsulate database access for workspace documents."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def base_query(self, workspace_id: str) -> Select[tuple[Document]]:
        """Return the base selectable for workspace document lookups."""

        return (
            select(Document)
            .options(
                selectinload(Document.uploaded_by_user),
                selectinload(Document.tags),
            )
            .where(Document.workspace_id == workspace_id)
        )

    async def get_document(
        self,
        *,
        workspace_id: str,
        document_id: str,
        include_deleted: bool = False,
    ) -> Document | None:
        """Return the document matching ``document_id`` for ``workspace_id``."""

        stmt = self.base_query(workspace_id).where(Document.id == document_id)
        if not include_deleted:
            stmt = stmt.where(Document.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        *,
        base_query: Select[tuple[Document]],
        order_by: Iterable,
    ) -> list[Document]:
        """Execute ``base_query`` applying ``order_by`` and return documents."""

        stmt = base_query.order_by(*order_by)
        result = await self._session.execute(stmt)
        return list(result.scalars())


__all__ = ["DocumentsRepository"]
