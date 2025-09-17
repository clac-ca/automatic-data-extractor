"""Tests for the snapshot API."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.db import get_sessionmaker


def _create_sample_snapshot(
    client: TestClient,
    *,
    document_type: str = "invoice",
    title: str = "Q1 snapshot",
) -> dict[str, Any]:
    """Create a snapshot via the API and return the response payload."""

    payload = {
        "document_type": document_type,
        "title": title,
        "payload": {"rows": []},
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
    assert data["payload"] == created["payload"]
    assert data["updated_at"] != created["updated_at"]


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


def test_snapshot_payload_mutations_persist(app_client) -> None:
    client, _, _ = app_client

    created = _create_sample_snapshot(client)

    from backend.app.models import Snapshot

    session_factory = get_sessionmaker()

    with session_factory() as session:
        snapshot = session.get(Snapshot, created["snapshot_id"])
        assert snapshot is not None
        snapshot.payload["metadata"] = {"version": "1.0", "tags": ["initial"]}
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
        snapshot.payload["metadata"]["version"] = "2.0"
        snapshot.payload["metadata"]["tags"].append("updated")
        snapshot.payload.setdefault("notes", []).append({"author": "qa"})
        session.commit()

    response = client.get(f"/snapshots/{created['snapshot_id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["payload"]["metadata"]["version"] == "2.0"
    assert data["payload"]["metadata"]["tags"] == ["initial", "updated"]
    assert data["payload"]["notes"] == [{"author": "qa"}]

    with session_factory() as session:
        snapshot = session.get(Snapshot, created["snapshot_id"])
        assert snapshot is not None
        snapshot.payload["notes"][0]["status"] = "reviewed"
        session.commit()

    response = client.get(f"/snapshots/{created['snapshot_id']}")

    assert response.status_code == 200
    assert response.json()["payload"]["notes"][0] == {"author": "qa", "status": "reviewed"}


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
