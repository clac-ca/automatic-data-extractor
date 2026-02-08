"""Configuration publish-run validation contract tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from ade_api.common.ids import generate_uuid7
from tests.api.integration.configs.helpers import auth_headers, create_from_template

pytestmark = pytest.mark.asyncio


async def test_publish_does_not_require_prior_validation_digest(
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
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers=headers,
        json={
            "configuration_id": record["id"],
            "options": {"operation": "publish"},
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["operation"] == "publish"


async def test_publish_missing_config_returns_not_found(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)
    random_id = str(generate_uuid7())

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers=headers,
        json={
            "configuration_id": random_id,
            "options": {"operation": "publish"},
        },
    )
    assert response.status_code == 404
    assert random_id in str(response.json().get("detail", ""))
