"""Tests for the configuration revision API."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.db import get_sessionmaker
from backend.app.services.configuration_revisions import (
    ActiveConfigurationRevisionNotFoundError,
    ConfigurationRevisionMismatchError,
    resolve_configuration_revision,
)


def _create_sample_configuration_revision(
    client: TestClient,
    *,
    document_type: str = "invoice",
    title: str = "Q1 configuration",
    is_active: bool = False,
) -> dict[str, Any]:
    """Create a configuration revision via the API and return the payload."""

    payload = {
        "document_type": document_type,
        "title": title,
        "payload": {"rows": []},
        "is_active": is_active,
    }
    response = client.post("/configuration-revisions", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_configuration_revision_returns_persisted_revision(app_client) -> None:
    client, db_path, _ = app_client

    payload = {
        "document_type": "invoice",
        "title": "Initial configuration",
        "payload": {"values": [1, 2, 3]},
        "is_active": True,
    }

    response = client.post("/configuration-revisions", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["document_type"] == payload["document_type"]
    assert data["title"] == payload["title"]
    assert data["payload"] == payload["payload"]
    assert data["is_active"] is True
    datetime.fromisoformat(data["activated_at"])
    assert len(data["configuration_revision_id"]) == 26
    assert data["revision_number"] == 1
    datetime.fromisoformat(data["created_at"])
    datetime.fromisoformat(data["updated_at"])
    assert db_path.exists()


def test_create_configuration_revision_trims_strings(app_client) -> None:
    client, _, _ = app_client

    payload = {
        "document_type": "  invoice  ",
        "title": "  Needs trimming  ",
        "payload": {},
    }

    response = client.post("/configuration-revisions", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["document_type"] == "invoice"
    assert data["title"] == "Needs trimming"
    assert data["activated_at"] is None


def test_list_configuration_revisions_orders_by_newest_first(app_client) -> None:
    client, _, _ = app_client

    first = _create_sample_configuration_revision(client, title="First")
    second = _create_sample_configuration_revision(client, title="Second")

    response = client.get("/configuration-revisions")

    assert response.status_code == 200
    data = response.json()
    assert [item["title"] for item in data] == ["Second", "First"]
    assert data[0]["configuration_revision_id"] == second["configuration_revision_id"]
    assert data[1]["configuration_revision_id"] == first["configuration_revision_id"]


def test_get_configuration_revision_returns_404_for_missing_resource(app_client) -> None:
    client, _, _ = app_client

    response = client.get("/configuration-revisions/does-not-exist")

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "Configuration revision 'does-not-exist' was not found"
    )


def test_update_configuration_revision_mutates_fields(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration_revision(client)
    configuration_revision_id = created["configuration_revision_id"]

    response = client.patch(
        f"/configuration-revisions/{configuration_revision_id}",
        json={"title": "Updated title", "is_active": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated title"
    assert data["is_active"] is True
    datetime.fromisoformat(data["activated_at"])
    assert data["payload"] == created["payload"]
    assert data["updated_at"] != created["updated_at"]


def test_activating_revision_demotes_previous_revision(app_client) -> None:
    client, _, _ = app_client

    first = _create_sample_configuration_revision(
        client, title="Draft 1", is_active=True
    )
    second = _create_sample_configuration_revision(client, title="Draft 2")

    publish_response = client.patch(
        f"/configuration-revisions/{second['configuration_revision_id']}",
        json={"is_active": True},
    )

    assert publish_response.status_code == 200
    assert (
        publish_response.json()["configuration_revision_id"]
        == second["configuration_revision_id"]
    )
    assert publish_response.json()["is_active"] is True

    first_refresh = client.get(
        f"/configuration-revisions/{first['configuration_revision_id']}"
    )
    assert first_refresh.status_code == 200
    first_data = first_refresh.json()
    assert first_data["is_active"] is False
    assert first_data["activated_at"] is None


def test_deactivating_revision_clears_active_state(app_client) -> None:
    client, _, _ = app_client

    active = _create_sample_configuration_revision(client, is_active=True)

    response = client.patch(
        f"/configuration-revisions/{active['configuration_revision_id']}",
        json={"is_active": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is False
    assert data["activated_at"] is None

    lookup = client.get(
        f"/configuration-revisions/active/{active['document_type']}"
    )
    assert lookup.status_code == 404


def test_update_configuration_revision_trims_title(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration_revision(client)

    response = client.patch(
        f"/configuration-revisions/{created['configuration_revision_id']}",
        json={"title": "  Updated Title  "},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"


def test_update_configuration_revision_requires_payload_when_provided(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration_revision(client)

    response = client.patch(
        f"/configuration-revisions/{created['configuration_revision_id']}",
        json={"payload": None},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("body", [{}, {"title": "   "}])
def test_update_configuration_revision_requires_non_empty_body(app_client, body) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration_revision(client)

    response = client.patch(
        f"/configuration-revisions/{created['configuration_revision_id']}",
        json=body,
    )

    assert response.status_code == 422


def test_update_configuration_revision_rejects_null_is_active(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration_revision(client)

    response = client.patch(
        f"/configuration-revisions/{created['configuration_revision_id']}",
        json={"is_active": None},
    )

    assert response.status_code == 422


def test_delete_configuration_revision_removes_record(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration_revision(client)

    delete_response = client.delete(
        f"/configuration-revisions/{created['configuration_revision_id']}"
    )
    assert delete_response.status_code == 204

    follow_up = client.get(
        f"/configuration-revisions/{created['configuration_revision_id']}"
    )
    assert follow_up.status_code == 404


def test_get_active_configuration_revision_endpoint_returns_active_revision(
    app_client,
) -> None:
    client, _, _ = app_client

    _create_sample_configuration_revision(client, title="Draft copy")
    active = _create_sample_configuration_revision(
        client, title="Active copy", is_active=True
    )

    response = client.get(
        f"/configuration-revisions/active/  {active['document_type']}  "
    )

    assert response.status_code == 200
    data = response.json()
    assert data["configuration_revision_id"] == active["configuration_revision_id"]
    assert data["is_active"] is True


def test_get_active_configuration_revision_endpoint_returns_404_when_missing(
    app_client,
) -> None:
    client, _, _ = app_client

    _create_sample_configuration_revision(client, title="Draft only")

    response = client.get("/configuration-revisions/active/invoice")

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "No active configuration revision found for 'invoice'"
    )


def test_get_active_configuration_revision_endpoint_rejects_blank_document_type(
    app_client,
) -> None:
    client, _, _ = app_client

    response = client.get("/configuration-revisions/active/   ")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert any(error.get("type") == "string_too_short" for error in detail)


def test_configuration_revision_payload_assignment_persists(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_configuration_revision(client)

    from backend.app.models import ConfigurationRevision

    session_factory = get_sessionmaker()

    with session_factory() as session:
        revision = session.get(
            ConfigurationRevision, created["configuration_revision_id"]
        )
        assert revision is not None
        updated_payload = dict(revision.payload)
        updated_payload["metadata"] = {"revision": "1.0", "tags": ["initial"]}
        revision.payload = updated_payload
        session.commit()

    response = client.get(
        f"/configuration-revisions/{created['configuration_revision_id']}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["payload"]["metadata"] == {
        "revision": "1.0",
        "tags": ["initial"],
    }

    with session_factory() as session:
        revision = session.get(
            ConfigurationRevision, created["configuration_revision_id"]
        )
        assert revision is not None
        updated_payload = dict(revision.payload)
        metadata = dict(updated_payload.get("metadata", {}))
        metadata["revision"] = "2.0"
        tags = list(metadata.get("tags", []))
        tags.append("updated")
        metadata["tags"] = tags
        notes = list(updated_payload.get("notes", []))
        notes.append({"author": "qa", "status": "reviewed"})
        updated_payload["metadata"] = metadata
        updated_payload["notes"] = notes
        revision.payload = updated_payload
        session.commit()

    response = client.get(
        f"/configuration-revisions/{created['configuration_revision_id']}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["payload"]["metadata"]["revision"] == "2.0"
    assert data["payload"]["metadata"]["tags"] == ["initial", "updated"]
    assert data["payload"]["notes"] == [{"author": "qa", "status": "reviewed"}]


def test_resolve_configuration_revision_defaults_to_active(app_client) -> None:
    client, _, _ = app_client

    active = _create_sample_configuration_revision(client, is_active=True)
    _create_sample_configuration_revision(client, title="Archived copy")

    session_factory = get_sessionmaker()
    with session_factory() as session:
        resolved = resolve_configuration_revision(
            session,
            document_type=active["document_type"],
            configuration_revision_id=None,
        )

    assert resolved.configuration_revision_id == active["configuration_revision_id"]


def test_resolve_configuration_revision_returns_requested_revision(app_client) -> None:
    client, _, _ = app_client

    active = _create_sample_configuration_revision(client, is_active=True)
    draft = _create_sample_configuration_revision(client, title="Older revision")

    session_factory = get_sessionmaker()
    with session_factory() as session:
        resolved = resolve_configuration_revision(
            session,
            document_type=active["document_type"],
            configuration_revision_id=draft["configuration_revision_id"],
        )

    assert resolved.configuration_revision_id == draft["configuration_revision_id"]


def test_resolve_configuration_revision_raises_for_mismatched_configuration(
    app_client,
) -> None:
    client, _, _ = app_client

    revision = _create_sample_configuration_revision(
        client, document_type="invoice", is_active=True
    )

    session_factory = get_sessionmaker()
    with session_factory() as session:
        with pytest.raises(ConfigurationRevisionMismatchError) as excinfo:
            resolve_configuration_revision(
                session,
                document_type="remittance",
                configuration_revision_id=revision["configuration_revision_id"],
            )

    assert (
        str(excinfo.value)
        == "Configuration revision "
        f"'{revision['configuration_revision_id']}' belongs to document type 'invoice', not 'remittance'"
    )


def test_resolve_configuration_revision_requires_active_revision_when_missing_id(
    app_client,
) -> None:
    client, _, _ = app_client

    _create_sample_configuration_revision(client, is_active=False)

    session_factory = get_sessionmaker()
    with session_factory() as session:
        with pytest.raises(ActiveConfigurationRevisionNotFoundError) as excinfo:
            resolve_configuration_revision(
                session,
                document_type="invoice",
                configuration_revision_id=None,
            )

    assert (
        str(excinfo.value)
        == "No active configuration revision found for 'invoice'"
    )


def test_revision_number_increments_per_configuration(app_client) -> None:
    client, _, _ = app_client

    first = _create_sample_configuration_revision(client)
    second = _create_sample_configuration_revision(client)

    assert first["revision_number"] == 1
    assert second["revision_number"] == 2

    other_configuration = _create_sample_configuration_revision(
        client, document_type="remittance"
    )
    assert other_configuration["revision_number"] == 1


def test_in_memory_sqlite_is_shared_across_threads(tmp_path, app_client_factory) -> None:
    """Ensure in-memory SQLite connections share a single database across threads."""

    documents_dir = tmp_path / "documents"

    with app_client_factory("sqlite:///:memory:", documents_dir) as client:
        payload = {
            "document_type": "invoice",
            "title": "Memory configuration",
            "payload": {"rows": [1, 2, 3]},
        }

        create_response = client.post("/configuration-revisions", json=payload)

        assert create_response.status_code == 201

        from sqlalchemy import select

        from backend.app.models import ConfigurationRevision

        session_factory = get_sessionmaker()

        def _fetch_titles() -> list[str]:
            with session_factory() as session:
                return session.scalars(select(ConfigurationRevision.title)).all()

        # Main thread should observe the inserted record.
        assert _fetch_titles() == ["Memory configuration"]

        # A background thread should hit the same in-memory database.
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_fetch_titles)
            assert future.result() == ["Memory configuration"]
