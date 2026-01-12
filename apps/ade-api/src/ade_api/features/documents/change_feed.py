"""Durable change feed helpers for documents."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from ade_api.common.time import utc_now
from ade_api.models import DocumentEvent
from ade_api.settings import Settings

logger = logging.getLogger(__name__)

DOCUMENT_EVENTS_PRUNE_INTERVAL_SECONDS = 600


@dataclass(slots=True)
class ChangeFeedPage:
    items: list[DocumentEvent]
    next_cursor: int


@dataclass(slots=True)
class ChangeCursorResolution:
    cursor: int
    oldest: int | None
    latest: int


class DocumentEventCursorError(Exception):
    """Base error for invalid change feed cursors."""


class DocumentEventCursorTooOld(DocumentEventCursorError):
    def __init__(self, *, oldest_cursor: int, latest_cursor: int) -> None:
        super().__init__("resync_required")
        self.oldest_cursor = oldest_cursor
        self.latest_cursor = latest_cursor


class DocumentEventsService:
    """Query the documents change feed."""

    def __init__(self, *, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def current_cursor(self, *, workspace_id: UUID) -> int:
        stmt = select(func.max(DocumentEvent.cursor)).where(
            DocumentEvent.workspace_id == workspace_id,
        )
        value = (self._session.execute(stmt)).scalar_one_or_none()
        return int(value or 0)

    def oldest_cursor(self, *, workspace_id: UUID) -> int | None:
        stmt = select(func.min(DocumentEvent.cursor)).where(
            DocumentEvent.workspace_id == workspace_id,
        )
        value = (self._session.execute(stmt)).scalar_one_or_none()
        return int(value) if value is not None else None

    def resolve_cursor(self, *, workspace_id: UUID, cursor: int) -> ChangeCursorResolution:
        oldest = self.oldest_cursor(workspace_id=workspace_id)
        latest = self.current_cursor(workspace_id=workspace_id)
        if oldest is not None and cursor < oldest:
            too_old = oldest > 1
            retention = self._settings.documents_change_feed_retention_period
            if not too_old and retention and retention.total_seconds() > 0:
                stmt = (
                    select(DocumentEvent.occurred_at)
                    .where(DocumentEvent.workspace_id == workspace_id)
                    .order_by(DocumentEvent.cursor.asc())
                    .limit(1)
                )
                oldest_occurred_at = (self._session.execute(stmt)).scalar_one_or_none()
                if oldest_occurred_at and utc_now() - oldest_occurred_at > retention:
                    too_old = True
            if too_old:
                raise DocumentEventCursorTooOld(oldest_cursor=oldest, latest_cursor=latest)
        if cursor > latest:
            cursor = latest
        return ChangeCursorResolution(cursor=cursor, oldest=oldest, latest=latest)

    def list_changes(
        self,
        *,
        workspace_id: UUID,
        cursor: int,
        limit: int,
        max_cursor: int | None = None,
    ) -> ChangeFeedPage:
        resolution = self.resolve_cursor(workspace_id=workspace_id, cursor=cursor)
        latest = resolution.latest
        cursor = resolution.cursor

        if max_cursor is not None and max_cursor > latest:
            max_cursor = latest

        effective_latest = max_cursor if max_cursor is not None else latest
        if cursor >= effective_latest:
            return ChangeFeedPage(items=[], next_cursor=effective_latest)

        stmt = (
            select(DocumentEvent)
            .where(
                DocumentEvent.workspace_id == workspace_id,
                DocumentEvent.cursor > cursor,
                DocumentEvent.cursor <= effective_latest,
            )
            .order_by(DocumentEvent.cursor.asc())
            .limit(limit)
        )
        result = self._session.execute(stmt)
        changes = list(result.scalars())
        if not changes:
            return ChangeFeedPage(items=[], next_cursor=effective_latest)
        next_cursor = int(changes[-1].cursor)
        return ChangeFeedPage(items=changes, next_cursor=next_cursor)

    def fetch_changes_after(
        self,
        *,
        workspace_id: UUID,
        cursor: int,
        limit: int,
    ) -> list[DocumentEvent]:
        stmt = (
            select(DocumentEvent)
            .where(
                DocumentEvent.workspace_id == workspace_id,
                DocumentEvent.cursor > cursor,
            )
            .order_by(DocumentEvent.cursor.asc())
            .limit(limit)
        )
        result = self._session.execute(stmt)
        return list(result.scalars())

    def prune(
        self,
        *,
        workspace_id: UUID | None = None,
        reference_time: datetime | None = None,
    ) -> None:
        retention = self._settings.documents_change_feed_retention_period
        if retention is None:
            return
        if isinstance(retention, timedelta) and retention.total_seconds() <= 0:
            return
        now = reference_time or utc_now()
        cutoff = now - retention
        stmt = delete(DocumentEvent).where(DocumentEvent.occurred_at < cutoff)
        if workspace_id is not None:
            stmt = stmt.where(DocumentEvent.workspace_id == workspace_id)
        self._session.execute(stmt)


async def run_document_events_pruner(
    *,
    settings: Settings,
    stop_event: asyncio.Event,
    session_factory: sessionmaker[Session],
) -> None:
    retention = settings.documents_change_feed_retention_period
    if retention is None:
        return
    if isinstance(retention, timedelta) and retention.total_seconds() <= 0:
        return

    def _prune_once() -> None:
        with session_factory() as session:
            with session.begin():
                service = DocumentEventsService(session=session, settings=settings)
                service.prune()

    while not stop_event.is_set():
        try:
            await asyncio.to_thread(_prune_once)
        except Exception:
            logger.warning("document_events.prune.failed", exc_info=True)

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=DOCUMENT_EVENTS_PRUNE_INTERVAL_SECONDS,
            )
        except TimeoutError:
            continue


__all__ = [
    "ChangeFeedPage",
    "DocumentEventCursorError",
    "DocumentEventCursorTooOld",
    "DocumentEventsService",
    "DOCUMENT_EVENTS_PRUNE_INTERVAL_SECONDS",
    "run_document_events_pruner",
]
