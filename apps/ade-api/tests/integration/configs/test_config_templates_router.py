"""Config template catalog endpoint tests."""

from __future__ import annotations

from typing import Any
from pathlib import Path

import pytest
from httpx import AsyncClient

from ade_api.settings import get_settings
from tests.utils import login

pytestmark = pytest.mark.asyncio


async def test_list_config_templates(
    async_client: AsyncClient, seed_identity: dict[str, Any]
) -> None:
    owner = seed_identity["workspace_owner"]
    token, _ = await login(async_client, email=owner["email"], password=owner["password"])

    response = await async_client.get(
        "/api/v1/config-templates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    settings = get_settings()
    expected_ids = {
        path.name
        for path in Path(settings.config_templates_source_dir).iterdir()
        if path.is_dir()
    }

    template_ids = {item["id"] for item in payload}
    assert expected_ids.issubset(template_ids)

    if "default" in template_ids:
        default_entry = next((item for item in payload if item["id"] == "default"), None)
        assert default_entry is not None
        assert default_entry["name"] == "Default ADE Workspace Config"
