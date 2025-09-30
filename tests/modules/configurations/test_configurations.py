from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.core.message_hub import Message
from app.core.db.session import get_sessionmaker
from app.configurations.models import Configuration


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    token = client.cookies.get("ade_session")
    assert token, "Session cookie missing"
    return token


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
        latest = result.scalar_one_or_none() or 0
        version = overrides.get("version", latest + 1)

        configuration = Configuration(
            document_type=document_type,
            title=overrides.get("title", "Baseline configuration"),
            version=version,
            is_active=is_active,
            activated_at=activated_at,
            payload=overrides.get("payload", {"rules": []}),
        )
        if is_active:
            await session.execute(
                update(Configuration)
                .where(
                    Configuration.document_type == document_type,
                    Configuration.is_active.is_(True),
                )
                .values(is_active=False, activated_at=None)
            )
        session.add(configuration)
        await session.flush()
        configuration_id = str(configuration.id)
        await session.commit()
    return configuration_id


async def _get_configuration(configuration_id: str) -> Configuration | None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        return await session.get(Configuration, configuration_id)


@pytest.mark.asyncio
async def test_list_configurations_supports_filters(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Listing configurations should support document type and status filters."""

    inactive_id = await _create_configuration(document_type="invoice", is_active=False)
    active_id = await _create_configuration(document_type="invoice", is_active=True)
    await _create_configuration(document_type="receipt", is_active=True)

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("configurations.listed", capture)
    try:
        admin = seed_identity["admin"]
        token = await _login(async_client, admin["email"], admin["password"])
        workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"

        response = await async_client.get(
            f"{workspace_base}/configurations",
            params={"document_type": "invoice", "is_active": "true"},
            headers={
                "Authorization": f"Bearer {token}",
            },
        )
    finally:
        hub.unsubscribe("configurations.listed", capture)

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    identifiers = {item["configuration_id"] for item in payload}
    assert active_id in identifiers
    assert inactive_id not in identifiers

    assert len(events) == 1
    event = events[0]
    assert event.name == "configurations.listed"
    assert event.payload["count"] == 1
    assert event.payload["document_type"] == "invoice"
    assert event.payload["is_active"] is True


@pytest.mark.asyncio
async def test_create_configuration_assigns_next_version(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Creating a configuration should increment the version counter."""

    baseline_id = await _create_configuration(document_type="invoice")
    baseline = await _get_configuration(baseline_id)
    assert baseline is not None
    baseline_version = baseline.version

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("configuration.created", capture)
    try:
        admin = seed_identity["admin"]
        token = await _login(async_client, admin["email"], admin["password"])
        workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"

        response = await async_client.post(
            f"{workspace_base}/configurations",
            json={
                "document_type": "invoice",
                "title": "Updated rules",
                "payload": {"rules": ["A", "B"]},
            },
            headers={
                "Authorization": f"Bearer {token}",
            },
        )
    finally:
        hub.unsubscribe("configuration.created", capture)

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["document_type"] == "invoice"
    assert payload["version"] == baseline_version + 1
    assert payload["is_active"] is False

    configuration = await _get_configuration(payload["configuration_id"])
    assert configuration is not None
    assert configuration.version == baseline_version + 1

    assert events, "Expected a configuration.created event"
    event = events[0]
    assert event.name == "configuration.created"
    assert event.payload["version"] == baseline_version + 1


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
        admin = seed_identity["admin"]
        token = await _login(async_client, admin["email"], admin["password"])
        workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"

        response = await async_client.get(
            f"{workspace_base}/configurations/{configuration_id}",
            headers={
                "Authorization": f"Bearer {token}",
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


@pytest.mark.asyncio
async def test_read_configuration_not_found_returns_404(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Unknown configuration identifiers should yield a 404 response."""

    admin = seed_identity["admin"]
    token = await _login(async_client, admin["email"], admin["password"])
    workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"

    response = await async_client.get(
        f"{workspace_base}/configurations/does-not-exist",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_configuration_replaces_fields(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """PUT should replace mutable fields on the configuration."""

    configuration_id = await _create_configuration(title="Initial", payload={"rules": ["A"]})

    admin = seed_identity["admin"]
    token = await _login(async_client, admin["email"], admin["password"])
    workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"

    response = await async_client.put(
        f"{workspace_base}/configurations/{configuration_id}",
        json={
            "title": "Replaced",
            "payload": {"rules": ["B", "C"]},
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["title"] == "Replaced"
    assert payload["payload"] == {"rules": ["B", "C"]}

    configuration = await _get_configuration(configuration_id)
    assert configuration is not None
    assert configuration.title == "Replaced"
    assert configuration.payload == {"rules": ["B", "C"]}


@pytest.mark.asyncio
async def test_delete_configuration_removes_record(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """DELETE should remove the configuration and emit an event."""

    configuration_id = await _create_configuration()

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("configuration.deleted", capture)
    try:
        admin = seed_identity["admin"]
        token = await _login(async_client, admin["email"], admin["password"])
        workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"

        response = await async_client.delete(
            f"{workspace_base}/configurations/{configuration_id}",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )
    finally:
        hub.unsubscribe("configuration.deleted", capture)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["message"] == "Configuration deleted"
    assert await _get_configuration(configuration_id) is None

    assert events, "Expected deletion to emit an event"
    event = events[0]
    assert event.name == "configuration.deleted"
    assert event.payload["configuration_id"] == configuration_id


@pytest.mark.asyncio
async def test_activate_configuration_toggles_previous_active(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    """Activating a configuration should deactivate previous versions."""

    previous_id = await _create_configuration(document_type="invoice", is_active=True)
    target_id = await _create_configuration(document_type="invoice", is_active=False)

    admin = seed_identity["admin"]
    token = await _login(async_client, admin["email"], admin["password"])
    workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"

    response = await async_client.post(
        f"{workspace_base}/configurations/{target_id}/activate",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["configuration_id"] == target_id
    assert payload["is_active"] is True
    assert payload["activated_at"]

    new_active = await _get_configuration(target_id)
    assert new_active is not None and new_active.is_active is True
    previous = await _get_configuration(previous_id)
    assert previous is not None and previous.is_active is False


@pytest.mark.asyncio
async def test_list_active_configurations_returns_current(
    async_client: AsyncClient,
    app: FastAPI,
    seed_identity: dict[str, Any],
) -> None:
    """Active configurations endpoint should only return active versions."""

    invoice_id = await _create_configuration(document_type="invoice", is_active=True)
    receipt_id = await _create_configuration(document_type="receipt", is_active=True)
    await _create_configuration(document_type="invoice", is_active=False)

    hub = app.state.message_hub
    events: list[Message] = []

    async def capture(message: Message) -> None:
        events.append(message)

    hub.subscribe("configurations.list_active", capture)
    try:
        admin = seed_identity["admin"]
        token = await _login(async_client, admin["email"], admin["password"])
        workspace_base = f"/api/workspaces/{seed_identity['workspace_id']}"

        response = await async_client.get(
            f"{workspace_base}/configurations/active",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )
    finally:
        hub.unsubscribe("configurations.list_active", capture)

    assert response.status_code == 200
    payload = response.json()
    identifiers = {item["configuration_id"] for item in payload}
    assert identifiers == {invoice_id, receipt_id}

    assert events, "Expected list_active to emit an event"
    event = events[0]
    assert event.name == "configurations.list_active"
    assert event.payload["count"] == 2

