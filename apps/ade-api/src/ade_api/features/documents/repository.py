"""Data access helpers for document records."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from ade_api.models import File, FileKind


class DocumentsRepository:
    """Encapsulate database access for workspace documents."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def base_query(self, workspace_id: UUID) -> Select[tuple[File]]:
        """Return the base selectable for workspace document lookups."""

        return (
            select(File)
            .options(
                selectinload(File.uploaded_by_user),
                selectinload(File.assignee_user),
                selectinload(File.tags),
                selectinload(File.current_version),
            )
            .where(File.workspace_id == workspace_id, File.kind == FileKind.DOCUMENT)
        )

    def get_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        include_deleted: bool = False,
    ) -> File | None:
        """Return the document matching ``document_id`` for ``workspace_id``."""

        stmt = self.base_query(workspace_id).where(File.id == document_id)
        if not include_deleted:
            stmt = stmt.where(File.deleted_at.is_(None))
        result = self._session.execute(stmt)
        return result.scalar_one_or_none()

    def list_documents(
        self,
        *,
        base_query: Select[tuple[File]],
        order_by: Iterable,
    ) -> list[File]:
        """Execute ``base_query`` applying ``order_by`` and return documents."""

        stmt = base_query.order_by(*order_by)
        result = self._session.execute(stmt)
        return list(result.scalars())


__all__ = ["DocumentsRepository"]
