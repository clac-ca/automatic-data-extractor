"""Tests for the info endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from ade_api.settings import Settings

pytestmark = pytest.mark.asyncio


async def test_info_endpoint_returns_metadata(async_client: AsyncClient, settings: Settings) -> None:
    response = await async_client.get("/api/v1/info")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == settings.app_version
    assert payload["commitSha"] == settings.app_commit_sha
    assert payload.get("startedAt")
