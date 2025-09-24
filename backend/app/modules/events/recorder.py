"""Utilities for persisting domain events inline."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .repository import EventsRepository


async def persist_event(
    session: AsyncSession,
    *,
    name: str,
    payload: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    correlation_id: str | None = None,
) -> None:
    """Persist an event row derived from ``payload`` and ``metadata``."""

    repository = EventsRepository(session)
    payload_data = dict(payload or {})
    metadata_data = dict(metadata or {})

    entity_type = str(metadata_data.get("entity_type") or name.split(".", 1)[0])
    entity_id = (
        metadata_data.get("entity_id")
        or payload_data.get("entity_id")
        or payload_data.get("configuration_id")
        or payload_data.get("document_id")
        or payload_data.get("job_id")
    )
    if entity_id is None:
        return

    if "workspace_id" in metadata_data and "workspace_id" not in payload_data:
        payload_data["workspace_id"] = metadata_data["workspace_id"]

    request_id = (
        metadata_data.get("request_id")
        or metadata_data.get("correlation_id")
        or correlation_id
    )

    occurred_at = datetime.now(tz=UTC).isoformat(timespec="milliseconds")

    await repository.record_event(
        event_type=name,
        entity_type=entity_type,
        entity_id=str(entity_id),
        occurred_at=occurred_at,
        actor_type=metadata_data.get("actor_type"),
        actor_id=metadata_data.get("actor_id"),
        actor_label=metadata_data.get("actor_label"),
        source=metadata_data.get("source"),
        request_id=str(request_id) if request_id is not None else None,
        payload=payload_data,
    )


__all__ = ["persist_event"]
