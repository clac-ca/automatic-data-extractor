from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.db import get_sessionmaker
from backend.app.services.audit_log import (
    AuditEventRecord,
    list_entity_events,
    list_events,
    record_event,
)


@pytest.fixture
def db_session(app_client):
    client, _, _ = app_client
    del client
    session_factory = get_sessionmaker()
    with session_factory() as session:
        yield session


def test_record_event_generates_ulids_and_canonical_payload(db_session) -> None:
    record = AuditEventRecord(
        event_type="document.deleted",
        entity_type="document",
        entity_id="doc-1",
        payload={"b": 2, "a": 1},
    )

    first = record_event(db_session, record)
    assert len(first.audit_event_id) == 26
    assert list(first.payload.keys()) == ["a", "b"]

    second = record_event(db_session, record)
    assert second.audit_event_id != first.audit_event_id
    assert list(second.payload.keys()) == ["a", "b"]


def test_record_event_accepts_optional_metadata(db_session) -> None:
    occurred_at = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    record = AuditEventRecord(
        event_type="configuration.updated",
        entity_type="configuration",
        entity_id="config-1",
        actor_type="system",
        actor_id="svc-1",
        actor_label="scheduler",
        source="scheduler",
        request_id="req-123",
        occurred_at=occurred_at.isoformat().replace("+00:00", "Z"),
        payload=None,
    )

    event = record_event(db_session, record)
    assert event.actor_type == "system"
    assert event.actor_id == "svc-1"
    assert event.actor_label == "scheduler"
    assert event.source == "scheduler"
    assert event.request_id == "req-123"
    assert event.payload == {}
    assert event.occurred_at.endswith("+00:00")


def test_list_events_filters_and_paginates(db_session) -> None:
    base_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    records = [
        AuditEventRecord(
            event_type="document.deleted",
            entity_type="document",
            entity_id="doc-1",
            source="api",
            actor_type="user",
            actor_label="ops",
            occurred_at=base_time + timedelta(minutes=index),
            payload={"index": index},
        )
        for index in range(3)
    ]
    records.append(
        AuditEventRecord(
            event_type="document.uploaded",
            entity_type="document",
            entity_id="doc-2",
            source="api",
            occurred_at=base_time + timedelta(minutes=10),
        )
    )

    for record in records:
        record_event(db_session, record)

    first_page = list_events(db_session, limit=2, offset=0)
    assert first_page.total == 4
    assert len(first_page.events) == 2

    second_page = list_events(db_session, limit=2, offset=2)
    assert len(second_page.events) == 2
    assert {event.entity_id for event in second_page.events} <= {"doc-1", "doc-2"}

    filtered = list_events(
        db_session,
        event_type="document.deleted",
        entity_type="document",
        entity_id="doc-1",
        source="api",
    )
    assert filtered.total == 3
    assert all(event.event_type == "document.deleted" for event in filtered.events)

    actor_filtered = list_events(db_session, actor_label="ops")
    assert actor_filtered.total == 3
    assert all(event.actor_label == "ops" for event in actor_filtered.events)


def test_list_events_occurred_filters_include_same_day_boundaries(db_session) -> None:
    event_day = datetime(2024, 3, 20, tzinfo=timezone.utc)
    morning = event_day.replace(hour=9, minute=0)
    evening = event_day.replace(hour=17, minute=30)
    next_day = evening + timedelta(days=1)

    record_event(
        db_session,
        AuditEventRecord(
            event_type="document.accessed",
            entity_type="document",
            entity_id="doc-morning",
            occurred_at=morning,
        ),
    )
    record_event(
        db_session,
        AuditEventRecord(
            event_type="document.accessed",
            entity_type="document",
            entity_id="doc-evening",
            occurred_at=evening,
        ),
    )
    record_event(
        db_session,
        AuditEventRecord(
            event_type="document.accessed",
            entity_type="document",
            entity_id="doc-next-day",
            occurred_at=next_day,
        ),
    )

    before_results = list_events(db_session, occurred_before=evening)
    assert {event.entity_id for event in before_results.events} == {
        "doc-morning",
        "doc-evening",
    }

    after_results = list_events(db_session, occurred_after=morning)
    assert {event.entity_id for event in after_results.events} == {
        "doc-morning",
        "doc-evening",
        "doc-next-day",
    }

    bounded_results = list_events(
        db_session,
        occurred_after=morning.isoformat(),
        occurred_before=evening.isoformat(),
    )
    assert {event.entity_id for event in bounded_results.events} == {
        "doc-morning",
        "doc-evening",
    }


def test_list_entity_events_matches_generic(db_session) -> None:
    for suffix in range(2):
        record_event(
            db_session,
            AuditEventRecord(
                event_type="document.deleted",
                entity_type="document",
                entity_id="doc-entity",
                payload={"attempt": suffix},
            ),
        )

    generic = list_events(db_session, entity_type="document", entity_id="doc-entity")
    scoped = list_entity_events(db_session, entity_type="document", entity_id="doc-entity")

    assert scoped.total == generic.total
    assert [event.audit_event_id for event in scoped.events] == [
        event.audit_event_id for event in generic.events
    ]


def test_audit_events_endpoint_supports_filters(app_client) -> None:
    client, _, _ = app_client
    session_factory = get_sessionmaker()

    with session_factory() as session:
        record_event(
            session,
            AuditEventRecord(
                event_type="document.deleted",
                entity_type="document",
                entity_id="doc-api-1",
                source="api",
                actor_type="user",
                actor_label="ops",
            ),
        )
        record_event(
            session,
            AuditEventRecord(
                event_type="document.uploaded",
                entity_type="document",
                entity_id="doc-api-2",
                source="api",
            ),
        )

    response = client.get("/audit-events", params={"limit": 1})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 1

    filtered = client.get(
        "/audit-events",
        params={"entity_type": "document", "entity_id": "doc-api-1"},
    )
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["total"] == 1
    assert filtered_payload["items"][0]["entity_id"] == "doc-api-1"

    actor_filtered = client.get(
        "/audit-events",
        params={"actor_label": "ops"},
    )
    assert actor_filtered.status_code == 200
    actor_payload = actor_filtered.json()
    assert actor_payload["total"] == 1
    assert actor_payload["items"][0]["actor_label"] == "ops"

    invalid = client.get("/audit-events", params={"entity_type": "document"})
    assert invalid.status_code == 400
