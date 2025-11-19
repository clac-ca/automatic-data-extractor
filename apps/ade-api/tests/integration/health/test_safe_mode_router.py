"""Integration coverage for safe mode management endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from ade_api.features.system_settings.service import SAFE_MODE_DEFAULT_DETAIL
from ade_api.settings import get_settings
from tests.utils import login

pytestmark = pytest.mark.asyncio

_SETTINGS = get_settings()
CSRF_COOKIE = _SETTINGS.session_csrf_cookie_name


async def test_safe_mode_toggle_persists_state(
    async_client: AsyncClient, seed_identity: dict[str, dict[str, str]]
) -> None:
    """Safe mode state can be toggled and reflected in health checks."""

    admin = seed_identity["admin"]
    await login(async_client, email=admin["email"], password=admin["password"])
    csrf_token = async_client.cookies.get(CSRF_COOKIE)
    assert csrf_token
    headers = {"X-CSRF-Token": csrf_token}

    initial = await async_client.get("/api/v1/system/safe-mode")
    assert initial.status_code == 200
    payload = initial.json()
    assert payload == {"enabled": False, "detail": SAFE_MODE_DEFAULT_DETAIL}

    updated = await async_client.put(
        "/api/v1/system/safe-mode",
        json={"enabled": True, "detail": "Maintenance window"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is True

    reread = await async_client.get("/api/v1/system/safe-mode")
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
