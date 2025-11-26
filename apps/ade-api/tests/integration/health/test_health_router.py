"""Tests for the health module endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_endpoint_returns_ok(async_client: AsyncClient) -> None:
    """The /health endpoint should return a successful payload."""
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    payload = response.json()
    assert payload["status"] == "ok"
    assert any(component["name"] == "api" for component in payload["components"])
    assert all("detail" in component for component in payload["components"])
    assert "timestamp" in payload


async def test_health_endpoint_includes_safe_mode_component(
    async_client: AsyncClient,
    override_app_settings,
) -> None:
    """The /health endpoint should flag safe mode when enabled."""

    override_app_settings(safe_mode=True)
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    safe_mode_component = next(
        (component for component in payload["components"] if component["name"] == "safe-mode"),
        None,
    )
    assert safe_mode_component is not None
    assert safe_mode_component["status"] == "degraded"
    assert "ADE_SAFE_MODE" in safe_mode_component["detail"]
