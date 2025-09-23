from __future__ import annotations

from typing import Any

from pydantic import Field

from ...core.schema import BaseSchema


class EventRecord(BaseSchema):
    """Serialised representation of a persisted event."""

    event_id: str = Field(alias="id", serialization_alias="event_id")
    event_type: str
    entity_type: str
    entity_id: str
    occurred_at: str
    actor_type: str | None = None
    actor_id: str | None = None
    actor_label: str | None = None
    source: str | None = None
    request_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


__all__ = ["EventRecord"]
