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
