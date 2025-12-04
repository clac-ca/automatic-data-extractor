"""Tests for the meta versions endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_meta_versions_returns_versions(async_client: AsyncClient) -> None:
    """The /meta/versions endpoint should return version strings."""

    response = await async_client.get("/api/v1/meta/versions")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("ade_api"), str)
    assert isinstance(payload.get("ade_engine"), str)
