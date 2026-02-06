"""Configuration publish behavior tests."""

from __future__ import annotations

import anyio
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ade_db.models import Configuration, ConfigurationStatus
from ade_api.settings import Settings
from tests.integration.configs.helpers import auth_headers, config_path, create_from_template

pytestmark = pytest.mark.asyncio


async def test_publish_configuration_sets_active_and_digest(
    async_client: AsyncClient,
    seed_identity,
    db_session,
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
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "active"
    assert payload["content_digest"].startswith("sha256:")

    stmt = select(Configuration).where(
        Configuration.workspace_id == workspace_id,
        Configuration.id == record["id"],
    )

    def _load_config():
        return db_session.execute(stmt).scalar_one()

    config = await anyio.to_thread.run_sync(_load_config)
    assert config.status == "active"
    assert config.content_digest == payload["content_digest"]


async def test_publish_archives_previous_active(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)
    first = await create_from_template(
        async_client, workspace_id=workspace_id, headers=headers, display_name="First"
    )
    await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{first['id']}/publish",
        headers=headers,
        json=None,
    )
    second = await create_from_template(
        async_client, workspace_id=workspace_id, headers=headers, display_name="Second"
    )
    await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{second['id']}/publish",
        headers=headers,
        json=None,
    )

    stmt = select(Configuration).where(Configuration.workspace_id == workspace_id)

    def _load_configs():
        result = db_session.execute(stmt)
        return {str(row.id): row for row in result.scalars()}

    configs = await anyio.to_thread.run_sync(_load_configs)
    assert configs[str(first["id"])].status is ConfigurationStatus.ARCHIVED
    assert configs[str(second["id"])].status is ConfigurationStatus.ACTIVE


async def test_publish_returns_422_when_validation_fails(
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
    package_path = config_path(settings, workspace_id, record["id"]) / "src" / "ade_config" / "__init__.py"
    package_path.unlink()

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/publish",
        headers=headers,
        json=None,
    )
    assert response.status_code == 422
    problem = response.json()
    assert problem["type"] == "validation_error"
    assert problem.get("errors")


async def test_publish_returns_409_when_configuration_not_draft(
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
    assert response.status_code == 200, response.text

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/publish",
        headers=headers,
        json=None,
    )
    assert response.status_code == 409
    assert "draft" in (response.json().get("detail") or "").lower()
