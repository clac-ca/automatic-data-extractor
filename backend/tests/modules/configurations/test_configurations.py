from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select

from backend.app.core.message_hub import Message
from backend.app.db.session import get_sessionmaker
from backend.app.modules.configurations.models import Configuration


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/auth/token",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _create_configuration(**overrides: Any) -> str:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        is_active = overrides.get("is_active", False)
        activated_at = overrides.get("activated_at")
        if activated_at is None and is_active:
            activated_at = datetime.now(UTC).isoformat(timespec="seconds")

        document_type = overrides.get("document_type", "invoice")
        result = await session.execute(
            select(func.max(Configuration.version)).where(
                Configuration.document_type == document_type
            )
        )
        next_version = result.scalar_one_or_none() or 0
        version = overrides.get("version", next_version + 1)

        configuration = Configuration(
            document_type=document_type,
            title=overrides.get("title", "Baseline configuration"),
            version=version,
            is_active=is_active,
            activated_at=activated_at,
            payload=overrides.get("payload", {"rules": []}),
        )
        session.add(configuration)
        await session.flush()
        configuration_id = str(configuration.id)
        await session.commit()
    return configuration_id


@pytest.mark.asyncio
async def test_list_configurations_emits_event(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Listing configurations should return results and emit a hub event."""

    configuration_id = await _create_configuration()

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("configurations.listed", capture)
    try:
        member = seed_identity["member"]
        token = await _login(async_client, member["email"], member["password"])

        response = await async_client.get(
            "/configurations",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Workspace-ID": seed_identity["workspace_id"],
            },
        )
    finally:
        hub.unsubscribe("configurations.listed", capture)

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert any(item["configuration_id"] == configuration_id for item in payload)

    assert len(events) == 1
    event = events[0]
    assert event.name == "configurations.listed"
    assert event.payload["count"] >= 1
    assert event.metadata.get("workspace_id") == seed_identity["workspace_id"]
    assert event.metadata.get("actor_type") == "user"


@pytest.mark.asyncio
async def test_read_configuration_emits_view_event(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Fetching a single configuration should emit a view event."""

    configuration_id = await _create_configuration()

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("configuration.viewed", capture)
    try:
        member = seed_identity["member"]
        token = await _login(async_client, member["email"], member["password"])

        response = await async_client.get(
            f"/configurations/{configuration_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Workspace-ID": seed_identity["workspace_id"],
            },
        )
    finally:
        hub.unsubscribe("configuration.viewed", capture)

    assert response.status_code == 200
    payload = response.json()
    assert payload["configuration_id"] == configuration_id
    assert events, "Expected at least one event to be emitted"
    event = events[0]
    assert event.name == "configuration.viewed"
    assert event.payload["configuration_id"] == configuration_id
    assert event.metadata.get("workspace_id") == seed_identity["workspace_id"]


@pytest.mark.asyncio
async def test_read_configuration_not_found_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Unknown configuration identifiers should yield a 404 response."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.get(
        "/configurations/does-not-exist",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_configuration_events_timeline_returns_persisted_events(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Timeline endpoint should return events captured for a configuration."""

    configuration_id = await _create_configuration()
    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-ID": seed_identity["workspace_id"],
    }

    response = await async_client.get(
        f"/configurations/{configuration_id}",
        headers=headers,
    )
    assert response.status_code == 200

    timeline = await async_client.get(
        f"/configurations/{configuration_id}/events",
        headers=headers,
    )

    assert timeline.status_code == 200
    events = timeline.json()
    assert isinstance(events, list)
    assert events, "Expected at least one persisted event"

    first = events[0]
    assert first["event_type"] == "configuration.viewed"
    assert first["entity_id"] == configuration_id
    assert first["payload"]["configuration_id"] == configuration_id
    assert first["actor_type"] == "user"


@pytest.mark.asyncio
async def test_configuration_events_timeline_missing_configuration_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Timeline request for unknown configurations should return 404."""

    member = seed_identity["member"]
    token = await _login(async_client, member["email"], member["password"])

    response = await async_client.get(
        "/configurations/does-not-exist/events",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": seed_identity["workspace_id"],
        },
    )

    assert response.status_code == 404
