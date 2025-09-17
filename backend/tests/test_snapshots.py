"""Tests for the snapshot API."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.db import get_sessionmaker
from backend.app.services.snapshots import (
    PublishedSnapshotNotFoundError,
    SnapshotDocumentTypeMismatchError,
    resolve_snapshot,
)


def _create_sample_snapshot(
    client: TestClient,
    *,
    document_type: str = "invoice",
    title: str = "Q1 snapshot",
    is_published: bool = False,
) -> dict[str, Any]:
    """Create a snapshot via the API and return the response payload."""

    payload = {
        "document_type": document_type,
        "title": title,
        "payload": {"rows": []},
        "is_published": is_published,
    }
    response = client.post("/snapshots", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_snapshot_returns_persisted_snapshot(app_client) -> None:
    client, db_path, _ = app_client

    payload = {
        "document_type": "invoice",
        "title": "Initial snapshot",
        "payload": {"values": [1, 2, 3]},
        "is_published": True,
    }

    response = client.post("/snapshots", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["document_type"] == payload["document_type"]
    assert data["title"] == payload["title"]
    assert data["payload"] == payload["payload"]
    assert data["is_published"] is True
    datetime.fromisoformat(data["published_at"])
    assert len(data["snapshot_id"]) == 26
    # Ensure timestamps are ISO formatted strings
    datetime.fromisoformat(data["created_at"])
    datetime.fromisoformat(data["updated_at"])
    assert db_path.exists()


def test_create_snapshot_trims_strings(app_client) -> None:
    client, _, _ = app_client

    payload = {
        "document_type": "  invoice  ",
        "title": "  Needs trimming  ",
        "payload": {},
    }

    response = client.post("/snapshots", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["document_type"] == "invoice"
    assert data["title"] == "Needs trimming"
    assert data["published_at"] is None


def test_list_snapshots_orders_by_newest_first(app_client) -> None:
    client, _, _ = app_client

    first = _create_sample_snapshot(client, title="First")
    second = _create_sample_snapshot(client, title="Second")

    response = client.get("/snapshots")

    assert response.status_code == 200
    data = response.json()
    assert [item["title"] for item in data] == ["Second", "First"]
    assert data[0]["snapshot_id"] == second["snapshot_id"]
    assert data[1]["snapshot_id"] == first["snapshot_id"]


def test_get_snapshot_returns_404_for_missing_resource(app_client) -> None:
    client, _, _ = app_client

    response = client.get("/snapshots/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Snapshot 'does-not-exist' was not found"


def test_update_snapshot_mutates_fields(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_snapshot(client)
    snapshot_id = created["snapshot_id"]

    response = client.patch(
        f"/snapshots/{snapshot_id}",
        json={"title": "Updated title", "is_published": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated title"
    assert data["is_published"] is True
    datetime.fromisoformat(data["published_at"])
    assert data["payload"] == created["payload"]
    assert data["updated_at"] != created["updated_at"]


def test_publishing_snapshot_demotes_previous_version(app_client) -> None:
    client, _, _ = app_client

    first = _create_sample_snapshot(client, title="Draft 1", is_published=True)
    second = _create_sample_snapshot(client, title="Draft 2")

    publish_response = client.patch(
        f"/snapshots/{second['snapshot_id']}",
        json={"is_published": True},
    )

    assert publish_response.status_code == 200
    assert publish_response.json()["snapshot_id"] == second["snapshot_id"]
    assert publish_response.json()["is_published"] is True

    first_refresh = client.get(f"/snapshots/{first['snapshot_id']}")
    assert first_refresh.status_code == 200
    first_data = first_refresh.json()
    assert first_data["is_published"] is False
    assert first_data["published_at"] is None


def test_unpublishing_snapshot_clears_published_state(app_client) -> None:
    client, _, _ = app_client

    published = _create_sample_snapshot(client, is_published=True)

    response = client.patch(
        f"/snapshots/{published['snapshot_id']}",
        json={"is_published": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_published"] is False
    assert data["published_at"] is None

    lookup = client.get(f"/snapshots/published/{published['document_type']}")
    assert lookup.status_code == 404


def test_update_snapshot_trims_title(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_snapshot(client)

    response = client.patch(
        f"/snapshots/{created['snapshot_id']}",
        json={"title": "  Updated Title  "},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"


def test_update_snapshot_requires_payload_when_provided(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_snapshot(client)

    response = client.patch(f"/snapshots/{created['snapshot_id']}", json={"payload": None})

    assert response.status_code == 422


@pytest.mark.parametrize("body", [{}, {"title": "   "}])
def test_update_snapshot_requires_non_empty_body(app_client, body) -> None:
    client, _, _ = app_client

    created = _create_sample_snapshot(client)

    response = client.patch(f"/snapshots/{created['snapshot_id']}", json=body)

    assert response.status_code == 422


def test_update_snapshot_rejects_null_boolean(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_snapshot(client)

    response = client.patch(
        f"/snapshots/{created['snapshot_id']}",
        json={"is_published": None},
    )

    assert response.status_code == 422


def test_delete_snapshot_removes_record(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_snapshot(client)

    delete_response = client.delete(f"/snapshots/{created['snapshot_id']}")
    assert delete_response.status_code == 204

    follow_up = client.get(f"/snapshots/{created['snapshot_id']}")
    assert follow_up.status_code == 404


def test_get_published_snapshot_endpoint_returns_active_snapshot(app_client) -> None:
    client, _, _ = app_client

    _create_sample_snapshot(client, title="Draft copy")
    published = _create_sample_snapshot(
        client, title="Published copy", is_published=True
    )

    response = client.get(f"/snapshots/published/  {published['document_type']}  ")

    assert response.status_code == 200
    data = response.json()
    assert data["snapshot_id"] == published["snapshot_id"]
    assert data["is_published"] is True


def test_get_published_snapshot_endpoint_returns_404_when_missing(app_client) -> None:
    client, _, _ = app_client

    _create_sample_snapshot(client, title="Draft only")

    response = client.get("/snapshots/published/invoice")

    assert response.status_code == 404
    assert response.json()["detail"] == "No published snapshot found for document type 'invoice'"


def test_snapshot_payload_assignment_persists(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_snapshot(client)

    from backend.app.models import Snapshot

    session_factory = get_sessionmaker()

    with session_factory() as session:
        snapshot = session.get(Snapshot, created["snapshot_id"])
        assert snapshot is not None
        updated_payload = dict(snapshot.payload)
        updated_payload["metadata"] = {"version": "1.0", "tags": ["initial"]}
        snapshot.payload = updated_payload
        session.commit()

    response = client.get(f"/snapshots/{created['snapshot_id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["payload"]["metadata"] == {
        "version": "1.0",
        "tags": ["initial"],
    }

    with session_factory() as session:
        snapshot = session.get(Snapshot, created["snapshot_id"])
        assert snapshot is not None
        updated_payload = dict(snapshot.payload)
        metadata = dict(updated_payload.get("metadata", {}))
        metadata["version"] = "2.0"
        tags = list(metadata.get("tags", []))
        tags.append("updated")
        metadata["tags"] = tags
        notes = list(updated_payload.get("notes", []))
        notes.append({"author": "qa", "status": "reviewed"})
        updated_payload["metadata"] = metadata
        updated_payload["notes"] = notes
        snapshot.payload = updated_payload
        session.commit()

    response = client.get(f"/snapshots/{created['snapshot_id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["payload"]["metadata"]["version"] == "2.0"
    assert data["payload"]["metadata"]["tags"] == ["initial", "updated"]
    assert data["payload"]["notes"] == [{"author": "qa", "status": "reviewed"}]


def test_resolve_snapshot_defaults_to_published(app_client) -> None:
    client, _, _ = app_client

    published = _create_sample_snapshot(client, is_published=True)
    _create_sample_snapshot(client, title="Archived copy")

    session_factory = get_sessionmaker()
    with session_factory() as session:
        resolved = resolve_snapshot(
            session,
            document_type=published["document_type"],
            snapshot_id=None,
        )

    assert resolved.snapshot_id == published["snapshot_id"]


def test_resolve_snapshot_returns_requested_snapshot(app_client) -> None:
    client, _, _ = app_client

    published = _create_sample_snapshot(client, is_published=True)
    draft = _create_sample_snapshot(client, title="Older version")

    session_factory = get_sessionmaker()
    with session_factory() as session:
        resolved = resolve_snapshot(
            session,
            document_type=published["document_type"],
            snapshot_id=draft["snapshot_id"],
        )

    assert resolved.snapshot_id == draft["snapshot_id"]


def test_resolve_snapshot_raises_for_mismatched_document_type(app_client) -> None:
    client, _, _ = app_client

    snapshot = _create_sample_snapshot(client, document_type="invoice", is_published=True)

    session_factory = get_sessionmaker()
    with session_factory() as session:
        with pytest.raises(SnapshotDocumentTypeMismatchError) as excinfo:
            resolve_snapshot(
                session,
                document_type="remittance",
                snapshot_id=snapshot["snapshot_id"],
            )

    assert (
        str(excinfo.value)
        == f"Snapshot '{snapshot['snapshot_id']}' belongs to document type 'invoice', not 'remittance'"
    )


def test_resolve_snapshot_requires_published_snapshot_when_missing_id(app_client) -> None:
    client, _, _ = app_client

    _create_sample_snapshot(client, is_published=False)

    session_factory = get_sessionmaker()
    with session_factory() as session:
        with pytest.raises(PublishedSnapshotNotFoundError) as excinfo:
            resolve_snapshot(session, document_type="invoice", snapshot_id=None)

    assert str(excinfo.value) == "No published snapshot found for document type 'invoice'"


def test_in_memory_sqlite_is_shared_across_threads(tmp_path, app_client_factory) -> None:
    """Ensure in-memory SQLite connections share a single database across threads."""

    documents_dir = tmp_path / "documents"

    with app_client_factory("sqlite:///:memory:", documents_dir) as client:
        payload = {
            "document_type": "invoice",
            "title": "Memory snapshot",
            "payload": {"rows": [1, 2, 3]},
        }

        create_response = client.post("/snapshots", json=payload)

        assert create_response.status_code == 201

        from sqlalchemy import select

        from backend.app.models import Snapshot

        session_factory = get_sessionmaker()

        def _fetch_titles() -> list[str]:
            with session_factory() as session:
                return session.scalars(select(Snapshot.title)).all()

        # Main thread should observe the inserted record.
        assert _fetch_titles() == ["Memory snapshot"]

        # A background thread should hit the same in-memory database.
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_fetch_titles)
            assert future.result() == ["Memory snapshot"]
