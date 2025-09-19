"""Tests for the configuration API."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.db import get_sessionmaker
from backend.app.services.audit_log import AuditEventRecord, record_event
from backend.app.services.configurations import (
    ActiveConfigurationNotFoundError,
    ConfigurationMismatchError,
    resolve_configuration,
)


def _create_sample_configuration(
    client: TestClient,
    *,
    document_type: str = "invoice",
    title: str = "Q1 configuration",
    is_active: bool = False,
) -> dict[str, Any]:
    """Create a configuration via the API and return the payload."""

    payload = {
        "document_type": document_type,
        "title": title,
        "payload": {"rows": []},
        "is_active": is_active,
    }
    response = client.post("/configurations", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_configuration_returns_persisted_configuration(app_client) -> None:
    client, db_path, _ = app_client

    payload = {
        "document_type": "invoice",
        "title": "Initial configuration",
        "payload": {"values": [1, 2, 3]},
        "is_active": True,
    }

    response = client.post("/configurations", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["document_type"] == payload["document_type"]
    assert data["title"] == payload["title"]
    assert data["payload"] == payload["payload"]
    assert data["is_active"] is True
    datetime.fromisoformat(data["activated_at"])
    assert len(data["configuration_id"]) == 26
    assert data["version"] == 1
    datetime.fromisoformat(data["created_at"])
    datetime.fromisoformat(data["updated_at"])
    assert db_path.exists()


def test_create_configuration_trims_strings(app_client) -> None:
    client, _, _ = app_client

    payload = {
        "document_type": "  invoice  ",
        "title": "  Needs trimming  ",
        "payload": {},
    }

    response = client.post("/configurations", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["document_type"] == "invoice"
    assert data["title"] == "Needs trimming"
    assert data["activated_at"] is None


def test_list_configurations_orders_by_newest_first(app_client) -> None:
    client, _, _ = app_client

    first = _create_sample_configuration(client, title="First")
    second = _create_sample_configuration(client, title="Second")

    response = client.get("/configurations")

    assert response.status_code == 200
    data = response.json()
    assert [item["title"] for item in data] == ["Second", "First"]
    assert data[0]["configuration_id"] == second["configuration_id"]
    assert data[1]["configuration_id"] == first["configuration_id"]


def test_get_configuration_returns_404_for_missing_resource(app_client) -> None:
    client, _, _ = app_client

    response = client.get("/configurations/does-not-exist")

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "Configuration 'does-not-exist' was not found"
    )


def test_update_configuration_mutates_fields(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration(client)
    configuration_id = created["configuration_id"]

    response = client.patch(
        f"/configurations/{configuration_id}",
        json={"title": "Updated title", "is_active": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated title"
    assert data["is_active"] is True
    datetime.fromisoformat(data["activated_at"])
    assert data["payload"] == created["payload"]
    assert data["updated_at"] != created["updated_at"]


def test_activating_configuration_demotes_previous_version(app_client) -> None:
    client, _, _ = app_client

    first = _create_sample_configuration(
        client, title="Draft 1", is_active=True
    )
    second = _create_sample_configuration(client, title="Draft 2")

    publish_response = client.patch(
        f"/configurations/{second['configuration_id']}",
        json={"is_active": True},
    )

    assert publish_response.status_code == 200
    assert (
        publish_response.json()["configuration_id"]
        == second["configuration_id"]
    )
    assert publish_response.json()["is_active"] is True

    first_refresh = client.get(
        f"/configurations/{first['configuration_id']}"
    )
    assert first_refresh.status_code == 200
    first_data = first_refresh.json()
    assert first_data["is_active"] is False
    assert first_data["activated_at"] is None


def test_deactivating_configuration_clears_active_state(app_client) -> None:
    client, _, _ = app_client

    active = _create_sample_configuration(client, is_active=True)

    response = client.patch(
        f"/configurations/{active['configuration_id']}",
        json={"is_active": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is False
    assert data["activated_at"] is None

    lookup = client.get(
        f"/configurations/active/{active['document_type']}"
    )
    assert lookup.status_code == 404


def test_update_configuration_trims_title(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration(client)

    response = client.patch(
        f"/configurations/{created['configuration_id']}",
        json={"title": "  Updated Title  "},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"


def test_update_configuration_requires_payload_when_provided(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration(client)

    response = client.patch(
        f"/configurations/{created['configuration_id']}",
        json={"payload": None},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("body", [{}, {"title": "   "}])
def test_update_configuration_requires_non_empty_body(app_client, body) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration(client)

    response = client.patch(
        f"/configurations/{created['configuration_id']}",
        json=body,
    )

    assert response.status_code == 422


def test_update_configuration_rejects_null_is_active(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration(client)

    response = client.patch(
        f"/configurations/{created['configuration_id']}",
        json={"is_active": None},
    )

    assert response.status_code == 422


def test_delete_configuration_removes_record(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration(client)

    delete_response = client.delete(
        f"/configurations/{created['configuration_id']}"
    )
    assert delete_response.status_code == 204

    follow_up = client.get(
        f"/configurations/{created['configuration_id']}"
    )
    assert follow_up.status_code == 404


def test_create_configuration_records_audit_events(app_client) -> None:
    client, _, _ = app_client

    payload = {
        "document_type": "invoice",
        "title": "Initial config",
        "payload": {"rules": ["basic"]},
        "is_active": True,
    }

    response = client.post("/configurations", json=payload)
    assert response.status_code == 201
    configuration = response.json()

    events = client.get(
        "/audit-events",
        params={
            "entity_type": "configuration",
            "entity_id": configuration["configuration_id"],
        },
    )
    assert events.status_code == 200
    payload_events = events.json()

    assert payload_events["total"] == 2
    event_types = {item["event_type"] for item in payload_events["items"]}
    assert event_types == {"configuration.created", "configuration.activated"}

    created_event = next(
        item
        for item in payload_events["items"]
        if item["event_type"] == "configuration.created"
    )
    assert created_event["actor_label"] == "api"
    assert created_event["source"] == "api"
    assert created_event["payload"]["title"] == payload["title"]
    assert created_event["payload"]["version"] == configuration["version"]
    assert created_event["payload"]["is_active"] is True

    activated_event = next(
        item
        for item in payload_events["items"]
        if item["event_type"] == "configuration.activated"
    )
    assert activated_event["payload"]["is_active"] is True
    assert activated_event["actor_label"] == "api"


def test_update_configuration_appends_audit_events(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration(client, is_active=False)

    events = client.get(
        "/audit-events",
        params={
            "entity_type": "configuration",
            "entity_id": created["configuration_id"],
        },
    )
    assert events.status_code == 200
    assert events.json()["total"] == 1

    update_response = client.patch(
        f"/configurations/{created['configuration_id']}",
        json={"title": "Updated"},
    )
    assert update_response.status_code == 200

    after_update = client.get(
        "/audit-events",
        params={
            "entity_type": "configuration",
            "entity_id": created["configuration_id"],
        },
    )
    assert after_update.status_code == 200
    update_payload = after_update.json()
    assert update_payload["total"] == 2
    updated_event = next(
        item
        for item in update_payload["items"]
        if item["event_type"] == "configuration.updated"
    )
    assert updated_event["payload"]["changed_fields"] == ["title"]
    assert updated_event["actor_label"] == "api"

    activate_response = client.patch(
        f"/configurations/{created['configuration_id']}",
        json={"is_active": True},
    )
    assert activate_response.status_code == 200

    after_activation = client.get(
        "/audit-events",
        params={
            "entity_type": "configuration",
            "entity_id": created["configuration_id"],
        },
    )
    assert after_activation.status_code == 200
    activation_payload = after_activation.json()
    assert activation_payload["total"] == 4
    activation_events = {
        item["event_type"]: item
        for item in activation_payload["items"]
        if item["event_type"] in {"configuration.updated", "configuration.activated"}
    }
    assert "configuration.activated" in activation_events

    activated = activation_events["configuration.activated"]
    assert activated["payload"]["is_active"] is True
    assert activated["actor_label"] == "api"

    updated_activation = next(
        item
        for item in activation_payload["items"]
        if item["event_type"] == "configuration.updated"
        and "is_active" in item["payload"].get("changed_fields", [])
    )
    assert "is_active" in updated_activation["payload"]["changed_fields"]


def test_get_active_configuration_endpoint_returns_active_configuration(
    app_client,
) -> None:
    client, _, _ = app_client

    _create_sample_configuration(client, title="Draft copy")
    active = _create_sample_configuration(
        client, title="Active copy", is_active=True
    )

    response = client.get(
        f"/configurations/active/  {active['document_type']}  "
    )

    assert response.status_code == 200
    data = response.json()
    assert data["configuration_id"] == active["configuration_id"]
    assert data["is_active"] is True


def test_get_active_configuration_endpoint_returns_404_when_missing(
    app_client,
) -> None:
    client, _, _ = app_client

    _create_sample_configuration(client, title="Draft only")

    response = client.get("/configurations/active/invoice")

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "No active configuration found for 'invoice'"
    )


def test_get_active_configuration_endpoint_rejects_blank_document_type(
    app_client,
) -> None:
    client, _, _ = app_client

    response = client.get("/configurations/active/   ")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert any(error.get("type") == "string_too_short" for error in detail)


def test_configuration_payload_assignment_persists(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration(client)

    from backend.app.models import Configuration

    session_factory = get_sessionmaker()

    with session_factory() as session:
        configuration = session.get(
            Configuration, created["configuration_id"]
        )
        assert configuration is not None
        updated_payload = dict(configuration.payload)
        updated_payload["metadata"] = {"version": "1.0", "tags": ["initial"]}
        configuration.payload = updated_payload
        session.commit()

    response = client.get(
        f"/configurations/{created['configuration_id']}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["payload"]["metadata"] == {
        "version": "1.0",
        "tags": ["initial"],
    }

    with session_factory() as session:
        configuration = session.get(
            Configuration, created["configuration_id"]
        )
        assert configuration is not None
        updated_payload = dict(configuration.payload)
        metadata = dict(updated_payload.get("metadata", {}))
        metadata["version"] = "2.0"
        tags = list(metadata.get("tags", []))
        tags.append("updated")
        metadata["tags"] = tags
        notes = list(updated_payload.get("notes", []))
        notes.append({"author": "qa", "status": "reviewed"})
        updated_payload["metadata"] = metadata
        updated_payload["notes"] = notes
        configuration.payload = updated_payload
        session.commit()

    response = client.get(
        f"/configurations/{created['configuration_id']}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["payload"]["metadata"]["version"] == "2.0"
    assert data["payload"]["metadata"]["tags"] == ["initial", "updated"]
    assert data["payload"]["notes"] == [{"author": "qa", "status": "reviewed"}]


def test_resolve_configuration_defaults_to_active(app_client) -> None:
    client, _, _ = app_client

    active = _create_sample_configuration(client, is_active=True)
    _create_sample_configuration(client, title="Archived copy")

    session_factory = get_sessionmaker()
    with session_factory() as session:
        resolved = resolve_configuration(
            session,
            document_type=active["document_type"],
            configuration_id=None,
        )

    assert resolved.configuration_id == active["configuration_id"]


def test_resolve_configuration_returns_requested_configuration(app_client) -> None:
    client, _, _ = app_client

    active = _create_sample_configuration(client, is_active=True)
    draft = _create_sample_configuration(client, title="Older version")

    session_factory = get_sessionmaker()
    with session_factory() as session:
        resolved = resolve_configuration(
            session,
            document_type=active["document_type"],
            configuration_id=draft["configuration_id"],
        )

    assert resolved.configuration_id == draft["configuration_id"]


def test_resolve_configuration_raises_for_mismatched_configuration(
    app_client,
) -> None:
    client, _, _ = app_client

    configuration = _create_sample_configuration(
        client, document_type="invoice", is_active=True
    )

    session_factory = get_sessionmaker()
    with session_factory() as session:
        with pytest.raises(ConfigurationMismatchError) as excinfo:
            resolve_configuration(
                session,
                document_type="remittance",
                configuration_id=configuration["configuration_id"],
            )

    assert (
        str(excinfo.value)
        == "Configuration "
        f"'{configuration['configuration_id']}' belongs to document type 'invoice', not 'remittance'"
    )


def test_resolve_configuration_requires_active_configuration_when_missing_id(
    app_client,
) -> None:
    client, _, _ = app_client

    _create_sample_configuration(client, is_active=False)

    session_factory = get_sessionmaker()
    with session_factory() as session:
        with pytest.raises(ActiveConfigurationNotFoundError) as excinfo:
            resolve_configuration(
                session,
                document_type="invoice",
                configuration_id=None,
            )

    assert (
        str(excinfo.value)
        == "No active configuration found for 'invoice'"
    )


def test_version_increments_per_configuration(app_client) -> None:
    client, _, _ = app_client

    first = _create_sample_configuration(client)
    second = _create_sample_configuration(client)

    assert first["version"] == 1
    assert second["version"] == 2

    other_configuration = _create_sample_configuration(
        client, document_type="remittance"
    )
    assert other_configuration["version"] == 1


def test_in_memory_sqlite_is_shared_across_threads(tmp_path, app_client_factory) -> None:
    """Ensure in-memory SQLite connections share a single database across threads."""

    documents_dir = tmp_path / "documents"

    with app_client_factory("sqlite:///:memory:", documents_dir) as client:
        payload = {
            "document_type": "invoice",
            "title": "Memory configuration",
            "payload": {"rows": [1, 2, 3]},
        }

        create_response = client.post("/configurations", json=payload)

        assert create_response.status_code == 201

        from sqlalchemy import select

        from backend.app.models import Configuration

        session_factory = get_sessionmaker()

        def _fetch_titles() -> list[str]:
            with session_factory() as session:
                return session.scalars(select(Configuration.title)).all()

        # Main thread should observe the inserted record.
        assert _fetch_titles() == ["Memory configuration"]

        # A background thread should hit the same in-memory database.
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_fetch_titles)
            assert future.result() == ["Memory configuration"]


def test_configuration_audit_timeline_paginates_and_filters(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration(client)
    configuration_id = created["configuration_id"]

    session_factory = get_sessionmaker()
    base_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    with session_factory() as session:
        for index in range(3):
            record_event(
                session,
                AuditEventRecord(
                    event_type=f"configuration.test.{index}",
                    entity_type="configuration",
                    entity_id=configuration_id,
                    source="timeline-test",
                    occurred_at=base_time + timedelta(minutes=index),
                    payload={"index": index},
                ),
            )

    response = client.get(
        f"/configurations/{configuration_id}/audit-events",
        params={"limit": 2, "source": "timeline-test"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["entity"] == {
        "configuration_id": configuration_id,
        "document_type": created["document_type"],
        "title": created["title"],
        "version": created["version"],
        "is_active": created["is_active"],
    }
    assert payload["total"] == 3
    assert [item["event_type"] for item in payload["items"]] == [
        "configuration.test.2",
        "configuration.test.1",
    ]

    second_page = client.get(
        f"/configurations/{configuration_id}/audit-events",
        params={"limit": 2, "offset": 2, "source": "timeline-test"},
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload["total"] == 3
    assert [item["event_type"] for item in second_payload["items"]] == [
        "configuration.test.0",
    ]

    filtered = client.get(
        f"/configurations/{configuration_id}/audit-events",
        params={
            "event_type": "configuration.test.1",
            "source": "timeline-test",
        },
    )
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["total"] == 1
    assert filtered_payload["items"][0]["event_type"] == "configuration.test.1"


def test_configuration_audit_timeline_summary_tracks_updates(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration(client)
    configuration_id = created["configuration_id"]

    update_response = client.patch(
        f"/configurations/{configuration_id}",
        json={"title": "Updated", "is_active": True},
    )
    assert update_response.status_code == 200
    updated = update_response.json()

    response = client.get(f"/configurations/{configuration_id}/audit-events")
    assert response.status_code == 200
    payload = response.json()
    assert payload["entity"] == {
        "configuration_id": configuration_id,
        "document_type": updated["document_type"],
        "title": updated["title"],
        "version": updated["version"],
        "is_active": updated["is_active"],
    }


def test_configuration_audit_timeline_returns_404_for_missing_configuration(app_client) -> None:
    client, _, _ = app_client

    response = client.get("/configurations/does-not-exist/audit-events")

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "Configuration 'does-not-exist' was not found"
    )
