"""Helpers for recording and querying audit events."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..models import AuditEvent

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AuditEventRecord:
    """Input payload accepted by :func:`record_event`."""

    event_type: str
    entity_type: str
    entity_id: str
    payload: dict[str, Any] | None = None
    actor_type: str | None = None
    actor_id: str | None = None
    actor_label: str | None = None
    source: str | None = None
    request_id: str | None = None
    occurred_at: datetime | str | None = None


@dataclass(slots=True)
class AuditEventQueryResult:
    """Container for a page of audit events."""

    events: list[AuditEvent]
    total: int
    limit: int
    offset: int


def _normalise_datetime(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)

    if isinstance(value, str):
        candidate = value.strip()
        if candidate.endswith(("Z", "z")):
            candidate = f"{candidate[:-1]}+00:00"
        parsed = datetime.fromisoformat(candidate)
    else:
        parsed = value

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed


def _normalise_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    # Serialise with sorted keys so retries emit identical JSON structures.
    serialised = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return json.loads(serialised)


def _apply_filters(statement: Select[AuditEvent], filters: dict[str, Any]) -> Select[AuditEvent]:
    if entity_type := filters.get("entity_type"):
        statement = statement.where(AuditEvent.entity_type == entity_type)
    if entity_id := filters.get("entity_id"):
        statement = statement.where(AuditEvent.entity_id == entity_id)
    if event_type := filters.get("event_type"):
        statement = statement.where(AuditEvent.event_type == event_type)
    if actor_type := filters.get("actor_type"):
        statement = statement.where(AuditEvent.actor_type == actor_type)
    if actor_id := filters.get("actor_id"):
        statement = statement.where(AuditEvent.actor_id == actor_id)
    if actor_label := filters.get("actor_label"):
        statement = statement.where(AuditEvent.actor_label == actor_label)
    if source := filters.get("source"):
        statement = statement.where(AuditEvent.source == source)
    if request_id := filters.get("request_id"):
        statement = statement.where(AuditEvent.request_id == request_id)

    occurred_after = filters.get("occurred_after")
    if occurred_after is not None:
        occurred_after_iso = _normalise_datetime(occurred_after).isoformat()
        statement = statement.where(AuditEvent.occurred_at >= occurred_after_iso)

    occurred_before = filters.get("occurred_before")
    if occurred_before is not None:
        occurred_before_iso = _normalise_datetime(occurred_before).isoformat()
        statement = statement.where(AuditEvent.occurred_at <= occurred_before_iso)

    return statement


def record_event(
    db: Session,
    event: AuditEventRecord,
    *,
    commit: bool = True,
) -> AuditEvent:
    """Persist an audit event and return the stored row."""

    occurred_at = _normalise_datetime(event.occurred_at).isoformat()
    payload = _normalise_payload(event.payload)

    model = AuditEvent(
        event_type=event.event_type,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        occurred_at=occurred_at,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        actor_label=event.actor_label,
        source=event.source,
        request_id=event.request_id,
        payload=payload,
    )
    db.add(model)

    try:
        if commit:
            db.commit()
            db.refresh(model)
        else:
            db.flush()
    except SQLAlchemyError:
        logger.exception(
            "Failed to record audit event",
            extra={
                "event_type": event.event_type,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
            },
        )
        if commit:
            db.rollback()
        raise

    return model


def list_events(
    db: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    event_type: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_type: str | None = None,
    actor_id: str | None = None,
    actor_label: str | None = None,
    source: str | None = None,
    request_id: str | None = None,
    occurred_after: datetime | str | None = None,
    occurred_before: datetime | str | None = None,
) -> AuditEventQueryResult:
    """Return audit events ordered by recency with optional filters."""

    if limit <= 0:
        raise ValueError("limit must be positive")
    if offset < 0:
        raise ValueError("offset cannot be negative")

    filters = {
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "actor_label": actor_label,
        "source": source,
        "request_id": request_id,
        "occurred_after": occurred_after,
        "occurred_before": occurred_before,
    }

    filtered_statement = _apply_filters(select(AuditEvent), filters)
    ordered_statement = filtered_statement.order_by(
        AuditEvent.occurred_at.desc(), AuditEvent.audit_event_id.desc()
    )

    total_statement = select(func.count()).select_from(filtered_statement.subquery())
    total = db.scalar(total_statement) or 0

    events = list(db.scalars(ordered_statement.offset(offset).limit(limit)))
    return AuditEventQueryResult(events=events, total=total, limit=limit, offset=offset)


def list_entity_events(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    limit: int = 50,
    offset: int = 0,
    event_type: str | None = None,
    source: str | None = None,
    request_id: str | None = None,
    occurred_after: datetime | str | None = None,
    occurred_before: datetime | str | None = None,
) -> AuditEventQueryResult:
    """Return events for a specific entity."""

    return list_events(
        db,
        limit=limit,
        offset=offset,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        source=source,
        request_id=request_id,
        occurred_after=occurred_after,
        occurred_before=occurred_before,
    )


__all__ = [
    "AuditEventRecord",
    "AuditEventQueryResult",
    "record_event",
    "list_events",
    "list_entity_events",
]
