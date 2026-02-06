"""Configuration creation and listing tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from ade_api.settings import Settings
from tests.api.integration.configs.helpers import auth_headers, config_path, create_from_template

pytestmark = pytest.mark.asyncio


async def test_create_configuration_from_template(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)

    record = await create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )

    path = config_path(settings, workspace_id, record["id"])
    assert path.exists()
    init_file = path / "src" / "ade_config" / "__init__.py"
    settings_file = path / "settings.toml"
    assert init_file.exists()
    assert settings_file.exists()


async def test_clone_configuration_creates_copy(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)

    source = await create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )

    clone_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations",
        headers=headers,
        json={
            "display_name": "Cloned Config",
            "source": {"type": "clone", "configuration_id": source["id"]},
        },
    )
    assert clone_response.status_code == 201, clone_response.text
    clone = clone_response.json()
    assert clone["display_name"] == "Cloned Config"
    clone_path = config_path(settings, workspace_id, clone["id"])
    assert clone_path.exists()
    assert (clone_path / "src" / "ade_config" / "__init__.py").exists()


async def test_list_and_read_configurations(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)
    record = await create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )

    list_response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/configurations",
        headers=headers,
    )
    assert list_response.status_code == 200, list_response.text
    payload = list_response.json()
    items = payload["items"]
    assert any(item["id"] == record["id"] for item in items)

    detail_response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    payload = detail_response.json()
    assert payload["id"] == record["id"]
    assert payload["display_name"] == record["display_name"]
