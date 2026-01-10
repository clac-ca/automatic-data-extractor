"""Data access helpers for document records."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from ade_api.models import Document


class DocumentsRepository:
    """Encapsulate database access for workspace documents."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def base_query(self, workspace_id: UUID) -> Select[tuple[Document]]:
        """Return the base selectable for workspace document lookups."""

        return (
            select(Document)
            .options(
                selectinload(Document.uploaded_by_user),
                selectinload(Document.assignee_user),
                selectinload(Document.tags),
            )
            .where(Document.workspace_id == workspace_id)
        )

    def get_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        include_deleted: bool = False,
    ) -> Document | None:
        """Return the document matching ``document_id`` for ``workspace_id``."""

        stmt = self.base_query(workspace_id).where(Document.id == document_id)
        if not include_deleted:
            stmt = stmt.where(Document.deleted_at.is_(None))
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def list_documents(
        self,
        *,
        base_query: Select[tuple[Document]],
        order_by: Iterable,
    ) -> list[Document]:
        """Execute ``base_query`` applying ``order_by`` and return documents."""

        stmt = base_query.order_by(*order_by)
        result = self._session.execute(stmt)
        return list(result.scalars())


__all__ = ["DocumentsRepository"]
