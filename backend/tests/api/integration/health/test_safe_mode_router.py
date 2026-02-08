"""Integration coverage for safe mode management endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from ade_api.features.system_settings.service import SAFE_MODE_DEFAULT_DETAIL
from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def test_safe_mode_toggle_persists_state(
    async_client: AsyncClient, seed_identity
) -> None:
    """Safe mode state can be toggled and reflected in health checks."""

    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    headers = {"X-API-Key": token}

    initial = await async_client.get("/api/v1/system/safemode", headers=headers)
    assert initial.status_code == 200
    payload = initial.json()
    assert payload == {"enabled": False, "detail": SAFE_MODE_DEFAULT_DETAIL}

    updated = await async_client.put(
        "/api/v1/system/safemode",
        json={"enabled": True, "detail": "Maintenance window"},
        headers=headers,
    )
    assert updated.status_code == 204
    assert updated.text == ""

    reread = await async_client.get("/api/v1/system/safemode", headers=headers)
    assert reread.status_code == 200
    reread_payload = reread.json()
    assert reread_payload["enabled"] is True
    assert reread_payload["detail"] == "Maintenance window"

    health = await async_client.get("/api/v1/health")
    assert health.status_code == 200
    components = health.json()["components"]
    safe_mode_component = next(
        (component for component in components if component.get("name") == "safe-mode"),
        None,
    )
    assert safe_mode_component is not None
    assert safe_mode_component["status"] == "degraded"
    assert safe_mode_component["detail"] == "Maintenance window"


async def test_safe_mode_read_requires_system_settings_permission(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    """Non-admins should be denied when reading safe mode status."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.get(
        "/api/v1/system/safemode",
        headers={"X-API-Key": token},
    )
    assert response.status_code == 403
