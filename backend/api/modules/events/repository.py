from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Event


class EventsRepository:
    """Persistence layer for domain events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_event(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: str,
        occurred_at: str,
        actor_type: str | None,
        actor_id: str | None,
        actor_label: str | None,
        source: str | None,
        request_id: str | None,
        payload: dict[str, Any],
    ) -> Event:
        """Persist a new event row and return it."""

        event = Event(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            occurred_at=occurred_at,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_label=actor_label,
            source=source,
            request_id=request_id,
            payload=payload,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_events_for_entity(
        self,
        *,
        entity_type: str,
        entity_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Event]:
        """Return events for a specific entity ordered by recency."""

        stmt: Select[tuple[Event]] = (
            select(Event)
            .where(Event.entity_type == entity_type, Event.entity_id == entity_id)
            .order_by(Event.occurred_at.desc(), Event.id.desc())
        )
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["EventsRepository"]
