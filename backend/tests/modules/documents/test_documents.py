"""Integration tests covering the documents module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from backend.app.core.message_hub import Message
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
