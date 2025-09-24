"""Integration tests covering the documents module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from backend.app.core.message_hub import Message
from backend.app.core.settings import get_settings, reset_settings_cache
from backend.app.db.session import get_sessionmaker
from backend.app.modules.documents.models import Document


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/auth/token",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _create_document(**overrides: Any) -> str:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(
            timespec="seconds"
        )
        document = Document(
            original_filename=overrides.get("original_filename", "statement.pdf"),
            content_type=overrides.get("content_type", "application/pdf"),
            byte_size=overrides.get("byte_size", 2048),
            sha256=overrides.get(
                "sha256",
                "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            ),
            stored_uri=overrides.get("stored_uri", "uploads/statement.pdf"),
            metadata_=overrides.get("metadata_", {"kind": "test"}),
            expires_at=overrides.get("expires_at", expires),
            produced_by_job_id=overrides.get("produced_by_job_id"),
        )
        session.add(document)
        await session.flush()
        document_id = str(document.id)
        await session.commit()
    return document_id


def _store_document_file(stored_uri: str, payload: bytes) -> Path:
    settings = get_settings()
    documents_dir = Path(settings.documents_dir)
    destination = documents_dir / stored_uri
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return destination


@pytest.mark.asyncio
async def test_upload_document_persists_file_and_emits_event(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Uploading a document should store bytes, persist metadata, and emit events."""

    payload = b"%PDF-1.4\n%%ADE"
    settings = get_settings()
    documents_dir = Path(settings.documents_dir)

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("document.uploaded", capture)
    try:
        member = seed_identity["member"]
        token = await _login(async_client, member["email"], member["password"])
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        }

        response = await async_client.post(
            "/documents",
            headers=headers,
            files={"file": ("statement.pdf", payload, "application/pdf")},
        )
    finally:
        hub.unsubscribe("document.uploaded", capture)

    assert response.status_code == 201, response.text
    body = response.json()
    document_id = body["document_id"]
    stored_uri = body["stored_uri"]
    assert stored_uri.startswith("uploads/")
    digest = hashlib.sha256(payload).hexdigest()
    assert body["sha256"] == digest

    file_path = documents_dir / stored_uri
    try:
        assert file_path.exists(), "Stored file should exist"
        assert file_path.read_bytes() == payload
    finally:
        file_path.unlink(missing_ok=True)

    assert events, "Expected the upload to emit a hub event"
    upload_event = events[0]
    assert upload_event.name == "document.uploaded"
    assert upload_event.payload["document_id"] == document_id
    assert upload_event.payload["sha256"] == digest

    timeline = await async_client.get(
        f"/documents/{document_id}/events",
        headers=headers,
    )
    assert timeline.status_code == 200
    timeline_events = timeline.json()
    assert any(item["event_type"] == "document.uploaded" for item in timeline_events)


@pytest.mark.asyncio
async def test_upload_document_rejects_unknown_job(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """A produced_by_job_id referencing a missing job should return 422."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": seed_identity["workspace_id"],
    }

    response = await async_client.post(
        "/documents",
        headers=headers,
        data={"produced_by_job_id": "job-missing"},
        files={"file": ("report.pdf", b"contents", "application/pdf")},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "invalid_job_reference"


@pytest.mark.asyncio
async def test_upload_document_rejects_invalid_expiration(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Supplying an invalid expires_at string should yield a validation error."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": seed_identity["workspace_id"],
    }

    response = await async_client.post(
        "/documents",
        headers=headers,
        data={"expires_at": "2020-01-01"},
        files={"file": ("report.pdf", b"contents", "application/pdf")},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "invalid_expiration"


@pytest.mark.asyncio
async def test_upload_document_enforces_max_upload_size(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uploads exceeding ADE_MAX_UPLOAD_BYTES should return HTTP 413."""

    monkeypatch.setenv("ADE_MAX_UPLOAD_BYTES", "4")
    reset_settings_cache()

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": seed_identity["workspace_id"],
    }

    try:
        response = await async_client.post(
            "/documents",
            headers=headers,
            files={"file": ("tiny.txt", b"too big", "text/plain")},
        )
    finally:
        monkeypatch.delenv("ADE_MAX_UPLOAD_BYTES", raising=False)
        reset_settings_cache()

    assert response.status_code == 413
    detail = response.json()["detail"]
    assert detail["error"] == "document_too_large"


@pytest.mark.asyncio
async def test_list_documents_emits_event(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Listing documents should return results and emit a hub event."""

    document_id = await _create_document()

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("documents.listed", capture)
    try:
        member = seed_identity["member"]
        token = await _login(async_client, member["email"], member["password"])

        response = await async_client.get(
            "/documents",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Workspace-ID": seed_identity["workspace_id"],
            },
        )
    finally:
        hub.unsubscribe("documents.listed", capture)

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert any(item["document_id"] == document_id for item in payload)

    assert len(events) == 1
    event = events[0]
    assert event.name == "documents.listed"
    assert event.payload["count"] >= 1
    assert event.metadata.get("workspace_id") == seed_identity["workspace_id"]
    assert event.metadata.get("actor_type") == "user"


@pytest.mark.asyncio
async def test_download_document_streams_file_and_emits_event(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Downloading a stored document should stream bytes and record events."""

    payload = b"%PDF-1.7\n%%ADE"
    stored_uri = "uploads/download.pdf"
    digest = hashlib.sha256(payload).hexdigest()

    document_id = await _create_document(
        stored_uri=stored_uri,
        byte_size=len(payload),
        sha256=digest,
    )
    file_path = _store_document_file(stored_uri, payload)

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("document.downloaded", capture)
    try:
        member = seed_identity["member"]
        token = await _login(async_client, member["email"], member["password"])
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        }

        response = await async_client.get(
            f"/documents/{document_id}/download",
            headers=headers,
        )
    finally:
        hub.unsubscribe("document.downloaded", capture)
        file_path.unlink(missing_ok=True)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"].lower()
    assert response.headers["x-document-sha256"] == digest
    assert response.content == payload

    assert events, "Expected a download event to be emitted"
    download_event = events[0]
    assert download_event.name == "document.downloaded"
    assert download_event.payload["document_id"] == document_id
    assert download_event.payload["sha256"] == digest

    timeline = await async_client.get(
        f"/documents/{document_id}/events",
        headers=headers,
    )
    assert timeline.status_code == 200
    timeline_events = timeline.json()
    assert any(item["event_type"] == "document.downloaded" for item in timeline_events)


@pytest.mark.asyncio
async def test_download_document_missing_file_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Missing stored files should return an explicit 404 error."""

    stored_uri = "uploads/missing.pdf"
    document_id = await _create_document(stored_uri=stored_uri)

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.get(
        f"/documents/{document_id}/download",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        },
    )

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["error"] == "document_file_missing"


@pytest.mark.asyncio
async def test_download_document_requires_workspace_membership(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Users without workspace membership should not be able to download documents."""

    payload = b"restricted"
    stored_uri = "uploads/restricted.pdf"
    digest = hashlib.sha256(payload).hexdigest()

    document_id = await _create_document(
        stored_uri=stored_uri,
        byte_size=len(payload),
        sha256=digest,
    )
    file_path = _store_document_file(stored_uri, payload)

    orphan = seed_identity["orphan"]
    token = await _login(async_client, orphan["email"], orphan["password"])

    try:
        response = await async_client.get(
            f"/documents/{document_id}/download",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Workspace-ID": seed_identity["workspace_id"],
            },
        )
    finally:
        file_path.unlink(missing_ok=True)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_document_metadata_merges_changes_and_emits_event(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Metadata updates should merge fields, drop removals, and emit events."""

    document_id = await _create_document(metadata_={"kind": "test", "source": "email"})

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("document.metadata.updated", capture)
    try:
        member = seed_identity["member"]
        token = await _login(async_client, member["email"], member["password"])
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        }

        response = await async_client.patch(
            f"/documents/{document_id}",
            headers=headers,
            json={"metadata": {"status": "processed", "kind": None}},
        )
    finally:
        hub.unsubscribe("document.metadata.updated", capture)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["metadata"] == {"source": "email", "status": "processed"}

    assert events, "Expected metadata updates to emit a hub event"
    event = events[0]
    assert event.name == "document.metadata.updated"
    assert event.payload["document_id"] == document_id
    assert event.payload["metadata"] == {"status": "processed"}
    assert event.payload["removed_keys"] == ["kind"]

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    timeline = await async_client.get(
        f"/documents/{document_id}/events",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        },
    )
    assert timeline.status_code == 200
    events_payload = timeline.json()
    metadata_event = next(
        item
        for item in events_payload
        if item["event_type"] == "document.metadata.updated"
    )
    assert metadata_event["payload"]["metadata"] == {"status": "processed"}
    assert metadata_event["payload"]["changed_keys"] == ["kind", "status"]
    assert metadata_event["payload"]["removed_keys"] == ["kind"]


@pytest.mark.asyncio
async def test_update_document_metadata_accepts_custom_event_type(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Clients may supply a custom event type and payload for metadata updates."""

    document_id = await _create_document(metadata_={"status": "pending"})

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("document.status.updated", capture)
    try:
        member = seed_identity["member"]
        token = await _login(async_client, member["email"], member["password"])
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        }

        response = await async_client.patch(
            f"/documents/{document_id}",
            headers=headers,
            json={
                "metadata": {"status": "complete"},
                "event_type": "document.status.updated",
                "event_payload": {"reason": "manual"},
            },
        )
    finally:
        hub.unsubscribe("document.status.updated", capture)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["metadata"] == {"status": "complete"}

    assert events, "Expected a custom metadata event to be emitted"
    event = events[0]
    assert event.name == "document.status.updated"
    assert event.payload["reason"] == "manual"
    assert event.payload["metadata"] == {"status": "complete"}

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    timeline = await async_client.get(
        f"/documents/{document_id}/events",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        },
    )
    assert timeline.status_code == 200
    events_payload = timeline.json()
    metadata_event = next(
        item
        for item in events_payload
        if item["event_type"] == "document.status.updated"
    )
    assert metadata_event["payload"]["metadata"] == {"status": "complete"}
    assert metadata_event["payload"]["reason"] == "manual"


@pytest.mark.asyncio
async def test_update_document_metadata_requires_workspace_membership_for_access(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Workspace outsiders should not be able to update metadata."""

    document_id = await _create_document()

    orphan = seed_identity["orphan"]
    token = await _login(async_client, orphan["email"], orphan["password"])

    response = await async_client.patch(
        f"/documents/{document_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        },
        json={"metadata": {"status": "denied"}},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_document_metadata_missing_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Updating a missing document should return 404."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.patch(
        "/documents/00000000000000000000000000",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        },
        json={"metadata": {"status": "missing"}},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_marks_record_and_emits_event(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Deleting a document should mark it deleted, remove the file, and emit events."""

    payload = b"obsolete"
    stored_uri = "uploads/delete.pdf"
    digest = hashlib.sha256(payload).hexdigest()

    document_id = await _create_document(
        stored_uri=stored_uri,
        byte_size=len(payload),
        sha256=digest,
    )
    file_path = _store_document_file(stored_uri, payload)

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("document.deleted", capture)
    try:
        member = seed_identity["member"]
        token = await _login(async_client, member["email"], member["password"])
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        }

        response = await async_client.request(
            "DELETE",
            f"/documents/{document_id}",
            headers=headers,
            json={"reason": "cleanup"},
        )
    finally:
        hub.unsubscribe("document.deleted", capture)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_id"] == document_id
    assert body["deleted_at"] is not None
    assert body["deleted_by"] == seed_identity["member"]["email"]
    assert body["delete_reason"] == "cleanup"
    assert not file_path.exists(), "Stored file should be removed"
    file_path.unlink(missing_ok=True)

    assert events, "Expected a deletion event to be emitted"
    event = events[0]
    assert event.name == "document.deleted"
    assert event.payload["document_id"] == document_id
    assert event.payload["delete_reason"] == "cleanup"

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    timeline = await async_client.get(
        f"/documents/{document_id}/events",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        },
    )
    assert timeline.status_code == 200
    events_payload = timeline.json()
    assert any(item["event_type"] == "document.deleted" for item in events_payload)


@pytest.mark.asyncio
async def test_delete_document_is_idempotent(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Repeated deletes should succeed without emitting duplicate events."""

    payload = b"redundant"
    stored_uri = "uploads/delete-idempotent.pdf"
    digest = hashlib.sha256(payload).hexdigest()

    document_id = await _create_document(
        stored_uri=stored_uri,
        byte_size=len(payload),
        sha256=digest,
    )
    file_path = _store_document_file(stored_uri, payload)

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("document.deleted", capture)
    try:
        member = seed_identity["member"]
        token = await _login(async_client, member["email"], member["password"])
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        }

        first = await async_client.request(
            "DELETE",
            f"/documents/{document_id}",
            headers=headers,
            json={"reason": "cleanup"},
        )
        assert first.status_code == 200
        first_body = first.json()
        first_deleted_at = first_body["deleted_at"]

        second = await async_client.request(
            "DELETE",
            f"/documents/{document_id}",
            headers=headers,
            json={"reason": "cleanup"},
        )
        assert second.status_code == 200
        second_body = second.json()
        assert second_body["deleted_at"] == first_deleted_at
        assert second_body["delete_reason"] == "cleanup"
    finally:
        hub.unsubscribe("document.deleted", capture)
        file_path.unlink(missing_ok=True)

    assert len(events) == 1


@pytest.mark.asyncio
async def test_delete_document_requires_workspace_membership_for_access(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Workspace outsiders should not be able to delete documents."""

    document_id = await _create_document()
    orphan = seed_identity["orphan"]
    token = await _login(async_client, orphan["email"], orphan["password"])

    response = await async_client.delete(
        f"/documents/{document_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_document_missing_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Deleting a missing document should return 404."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.delete(
        "/documents/00000000000000000000000000",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_read_document_emits_view_event(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Fetching a single document should emit a view event."""

    document_id = await _create_document()

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("document.viewed", capture)
    try:
        member = seed_identity["member"]
        token = await _login(async_client, member["email"], member["password"])

        response = await async_client.get(
            f"/documents/{document_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Workspace-ID": seed_identity["workspace_id"],
            },
        )
    finally:
        hub.unsubscribe("document.viewed", capture)

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == document_id
    assert events, "Expected at least one event to be emitted"
    event = events[0]
    assert event.name == "document.viewed"
    assert event.payload["document_id"] == document_id
    assert event.metadata.get("workspace_id") == seed_identity["workspace_id"]


@pytest.mark.asyncio
async def test_read_document_not_found_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Unknown document identifiers should yield a 404 response."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.get(
        "/documents/00000000000000000000000000",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_document_events_timeline_returns_persisted_events(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Timeline endpoint should return events captured for a document."""

    document_id = await _create_document()
    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": seed_identity["workspace_id"],
    }

    response = await async_client.get(f"/documents/{document_id}", headers=headers)
    assert response.status_code == 200

    timeline = await async_client.get(
        f"/documents/{document_id}/events",
        headers=headers,
    )

    assert timeline.status_code == 200
    events = timeline.json()
    assert isinstance(events, list)
    assert events, "Expected at least one persisted event"

    first = events[0]
    assert first["event_type"] == "document.viewed"
    assert first["entity_id"] == document_id
    assert first["payload"]["document_id"] == document_id
    assert first["actor_type"] == "user"


@pytest.mark.asyncio
async def test_document_events_timeline_missing_document_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Timeline request for unknown documents should return 404."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.get(
        "/documents/00000000000000000000000000/events",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        },
    )

    assert response.status_code == 404
