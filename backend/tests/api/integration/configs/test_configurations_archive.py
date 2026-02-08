"""Configuration archival tests."""

from __future__ import annotations

import anyio
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ade_db.models import Configuration, ConfigurationStatus
from tests.api.integration.configs.helpers import auth_headers, create_from_template

pytestmark = pytest.mark.asyncio


async def test_archive_configuration_sets_archived(
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

    stmt = select(Configuration).where(Configuration.id == record["id"])

    def _promote_to_active() -> None:
        config = db_session.execute(stmt).scalar_one()
        config.status = ConfigurationStatus.ACTIVE
        db_session.commit()

    await anyio.to_thread.run_sync(_promote_to_active)

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/archive",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "archived"


async def test_archive_draft_configuration_sets_archived(
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
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/archive",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "archived"


async def test_archive_archived_configuration_is_idempotent(
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

    stmt = select(Configuration).where(Configuration.id == record["id"])

    def _set_archived() -> None:
        config = db_session.execute(stmt).scalar_one()
        config.status = ConfigurationStatus.ARCHIVED
        db_session.commit()

    await anyio.to_thread.run_sync(_set_archived)

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/archive",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "archived"
