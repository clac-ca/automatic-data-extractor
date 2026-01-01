"""Durable change feed helpers for documents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ade_api.common.time import utc_now
from ade_api.models import DocumentChange, DocumentChangeType
from ade_api.settings import Settings


@dataclass(slots=True)
class ChangeFeedPage:
    items: list[DocumentChange]
    next_cursor: int


class DocumentChangeCursorError(Exception):
    """Base error for invalid change feed cursors."""


class DocumentChangeCursorTooOld(DocumentChangeCursorError):
    def __init__(self, *, latest_cursor: int) -> None:
        super().__init__("resync_required")
        self.latest_cursor = latest_cursor


class DocumentChangesService:
    """Persist and query the documents change feed."""

    def __init__(self, *, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def current_cursor(self, *, workspace_id: UUID) -> int:
        stmt = select(func.max(DocumentChange.cursor)).where(
            DocumentChange.workspace_id == workspace_id,
        )
        value = (await self._session.execute(stmt)).scalar_one_or_none()
        return int(value or 0)

    async def oldest_cursor(self, *, workspace_id: UUID) -> int | None:
        stmt = select(func.min(DocumentChange.cursor)).where(
            DocumentChange.workspace_id == workspace_id,
        )
        value = (await self._session.execute(stmt)).scalar_one_or_none()
        return int(value) if value is not None else None

    async def list_changes(
        self,
        *,
        workspace_id: UUID,
        cursor: int,
        limit: int,
    ) -> ChangeFeedPage:
        await self._prune_if_needed(workspace_id=workspace_id)

        oldest = await self.oldest_cursor(workspace_id=workspace_id)
        latest = await self.current_cursor(workspace_id=workspace_id)
        if oldest is not None and cursor < oldest:
            raise DocumentChangeCursorTooOld(latest_cursor=latest)

        if cursor >= latest:
            return ChangeFeedPage(items=[], next_cursor=latest)

        stmt = (
            select(DocumentChange)
            .where(
                DocumentChange.workspace_id == workspace_id,
                DocumentChange.cursor > cursor,
            )
            .order_by(DocumentChange.cursor.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        changes = list(result.scalars())
        if not changes:
            return ChangeFeedPage(items=[], next_cursor=latest)
        next_cursor = int(changes[-1].cursor)
        return ChangeFeedPage(items=changes, next_cursor=next_cursor)

    async def record_upsert(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        payload: dict[str, Any],
        occurred_at: datetime | None = None,
    ) -> DocumentChange:
        serialized = jsonable_encoder(payload)
        entry = DocumentChange(
            workspace_id=workspace_id,
            document_id=document_id,
            type=DocumentChangeType.UPSERT,
            payload=serialized,
            occurred_at=occurred_at or utc_now(),
        )
        self._session.add(entry)
        await self._session.flush()
        await self._prune_if_needed(
            workspace_id=workspace_id,
            reference_time=entry.occurred_at,
        )
        return entry

    async def record_deleted(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        occurred_at: datetime | None = None,
    ) -> DocumentChange:
        entry = DocumentChange(
            workspace_id=workspace_id,
            document_id=document_id,
            type=DocumentChangeType.DELETED,
            payload={},
            occurred_at=occurred_at or utc_now(),
        )
        self._session.add(entry)
        await self._session.flush()
        await self._prune_if_needed(
            workspace_id=workspace_id,
            reference_time=entry.occurred_at,
        )
        return entry

    async def _prune_if_needed(
        self,
        *,
        workspace_id: UUID,
        reference_time: datetime | None = None,
    ) -> None:
        retention = self._settings.documents_change_feed_retention_period
        if retention is None:
            return
        if isinstance(retention, timedelta) and retention.total_seconds() <= 0:
            return
        now = reference_time or utc_now()
        cutoff = now - retention
        stmt = delete(DocumentChange).where(
            DocumentChange.workspace_id == workspace_id,
            DocumentChange.occurred_at < cutoff,
        )
        await self._session.execute(stmt)


__all__ = [
    "ChangeFeedPage",
    "DocumentChangeCursorError",
    "DocumentChangeCursorTooOld",
    "DocumentChangesService",
]
