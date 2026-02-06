"""Configuration publish gating tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from ade_api.common.ids import generate_uuid7
from ade_api.settings import Settings
from tests.integration.configs.helpers import auth_headers, config_path, create_from_template

pytestmark = pytest.mark.asyncio


async def test_publish_requires_validation_digest(
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

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/publish",
        headers=headers,
        json=None,
    )
    assert response.status_code == 422, response.text
    payload = response.json()
    assert payload["detail"]["error"] == "validation_required"


async def test_publish_missing_config_returns_not_found(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)
    random_id = str(generate_uuid7())

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{random_id}/publish",
        headers=headers,
        json=None,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "configuration_not_found"


async def test_publish_requires_engine_dependency(
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
    pyproject = config_path(settings, workspace_id, record["id"]) / "pyproject.toml"
    pyproject.write_text(
        (
            "[project]\n"
            "name = \"ade_config\"\n"
            "version = \"0.1.0\"\n"
            "dependencies = [\"pandas\"]\n"
        ),
        encoding="utf-8",
    )

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/publish",
        headers=headers,
        json=None,
    )
    assert response.status_code == 422, response.text
    payload = response.json()
    assert payload["detail"]["error"] == "engine_dependency_missing"
