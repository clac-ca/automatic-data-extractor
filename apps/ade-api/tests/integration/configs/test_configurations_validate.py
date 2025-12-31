"""Configuration validation tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from ade_api.db import generate_uuid7
from ade_api.settings import Settings
from tests.integration.configs.helpers import auth_headers, config_path, create_from_template

pytestmark = pytest.mark.asyncio


async def test_validate_configuration_success(
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

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/validate",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["issues"] == []
    assert payload["content_digest"].startswith("sha256:")


async def test_validate_reports_issues_when_package_missing(
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
    package_path = (
        config_path(settings, workspace_id, record["id"]) / "src" / "ade_config" / "__init__.py"
    )
    package_path.unlink()

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/validate",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["issues"], "Expected issues when package import is broken"
    assert payload.get("content_digest") is None


async def test_validate_missing_config_returns_not_found(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)
    random_id = str(generate_uuid7())

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{random_id}/validate",
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "configuration_not_found"
