"""Integration coverage for runtime safe-mode settings endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from ade_api.features.admin_settings.service import DEFAULT_SAFE_MODE_DETAIL
from tests.api.utils import login

pytestmark = pytest.mark.asyncio


async def test_safe_mode_toggle_persists_state(
    async_client: AsyncClient, seed_identity
) -> None:
    """Safe mode state can be toggled and reflected in health checks."""

    admin = seed_identity.admin
    token, _ = await login(async_client, email=admin.email, password=admin.password)
    headers = {"X-API-Key": token}

    initial = await async_client.get("/api/v1/admin/settings", headers=headers)
    assert initial.status_code == 200
    payload = initial.json()
    assert payload["values"]["safeMode"] == {
        "enabled": False,
        "detail": DEFAULT_SAFE_MODE_DETAIL,
    }

    updated = await async_client.patch(
        "/api/v1/admin/settings",
        json={
            "revision": payload["revision"],
            "changes": {
                "safeMode": {
                    "enabled": True,
                    "detail": "Maintenance window",
                }
            },
        },
        headers=headers,
    )
    assert updated.status_code == 200

    reread = await async_client.get("/api/v1/admin/settings", headers=headers)
    assert reread.status_code == 200
    reread_payload = reread.json()
    assert reread_payload["values"]["safeMode"]["enabled"] is True
    assert reread_payload["values"]["safeMode"]["detail"] == "Maintenance window"

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
    """Non-admins should be denied when reading runtime settings."""

    member = seed_identity.member
    token, _ = await login(async_client, email=member.email, password=member.password)

    response = await async_client.get(
        "/api/v1/admin/settings",
        headers={"X-API-Key": token},
    )
    assert response.status_code == 403
