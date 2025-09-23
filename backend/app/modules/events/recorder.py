from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...core.message_hub import Message
from .repository import EventsRepository


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class PersistedEvent:
    event_type: str
    entity_type: str
    entity_id: str
    occurred_at: str
    actor_type: str | None
    actor_id: str | None
    actor_label: str | None
    source: str | None
    request_id: str | None
    payload: dict[str, Any]


class EventRecorder:
    """Subscriber that writes published messages to the events table."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __call__(self, message: Message) -> None:
        event = self._build_event(message)
        if event is None:
            return

        try:
            async with self._session_factory() as session:
                repository = EventsRepository(session)
                try:
                    await repository.record_event(
                        event_type=event.event_type,
                        entity_type=event.entity_type,
                        entity_id=event.entity_id,
                        occurred_at=event.occurred_at,
                        actor_type=event.actor_type,
                        actor_id=event.actor_id,
                        actor_label=event.actor_label,
                        source=event.source,
                        request_id=event.request_id,
                        payload=event.payload,
                    )
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
        except Exception:
            LOGGER.exception("Failed to persist event \"%s\"", message.name)

    def _build_event(self, message: Message) -> PersistedEvent | None:
        metadata = dict(message.metadata)
        payload = dict(message.payload)

        entity_type = str(metadata.get("entity_type") or message.name.split(".", 1)[0])
        entity_id_value = (
            metadata.get("entity_id")
            or payload.get("entity_id")
            or payload.get("document_id")
        )
        if entity_id_value is None:
            LOGGER.debug(
                "Skipping event \"%s\" because no entity identifier was provided",
                message.name,
            )
            return None

        if "workspace_id" in metadata and "workspace_id" not in payload:
            payload["workspace_id"] = metadata["workspace_id"]

        request_id = (
            metadata.get("request_id")
            or metadata.get("correlation_id")
            or message.correlation_id
        )

        occurred_at = datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")

        return PersistedEvent(
            event_type=message.name,
            entity_type=entity_type,
            entity_id=str(entity_id_value),
            occurred_at=occurred_at,
            actor_type=metadata.get("actor_type"),
            actor_id=metadata.get("actor_id"),
            actor_label=metadata.get("actor_label"),
            source=metadata.get("source"),
            request_id=str(request_id) if request_id is not None else None,
            payload=payload,
        )


__all__ = ["EventRecorder"]
