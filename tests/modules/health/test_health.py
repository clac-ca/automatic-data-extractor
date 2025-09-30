"""Tests for the health module endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok(async_client: AsyncClient) -> None:
    """The /health endpoint should return a successful payload."""
    response = await async_client.get("/api/health")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    payload = response.json()
    assert payload["status"] == "ok"
    assert any(component["name"] == "api" for component in payload["components"])
    assert all("detail" in component for component in payload["components"])
    assert "timestamp" in payload
