"""Configuration editing guards."""

from __future__ import annotations

import anyio
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ade_db.models import Configuration, ConfigurationStatus
from tests.api.integration.configs.helpers import auth_headers, create_from_template

pytestmark = pytest.mark.asyncio


async def test_editing_non_draft_rejected(
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
    base_url = f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}"
    stmt = select(Configuration).where(Configuration.id == record["id"])

    def _promote_to_active() -> None:
        config = db_session.execute(stmt).scalar_one()
        config.status = ConfigurationStatus.ACTIVE
        db_session.commit()

    await anyio.to_thread.run_sync(_promote_to_active)
    put_headers = dict(headers)
    put_headers["If-None-Match"] = "*"
    put_headers["Content-Type"] = "application/octet-stream"
    resp = await async_client.put(
        f"{base_url}/files/assets/blocked.txt?parents=1",
        headers=put_headers,
        content=b"forbidden",
    )
    assert resp.status_code == 409


async def test_file_listing_capabilities_follow_configuration_status(
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
    base_url = f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}"
    stmt = select(Configuration).where(Configuration.id == record["id"])

    response = await async_client.get(f"{base_url}/files", headers=headers)
    assert response.status_code == 200
    assert response.json()["capabilities"]["editable"] is True
    baseline_etag = response.headers.get("ETag")
    assert baseline_etag

    def _set_status(status: ConfigurationStatus) -> None:
        config = db_session.execute(stmt).scalar_one()
        config.status = status
        db_session.commit()

    await anyio.to_thread.run_sync(_set_status, ConfigurationStatus.ACTIVE)
    conditional_headers = dict(headers)
    conditional_headers["If-None-Match"] = baseline_etag
    response = await async_client.get(f"{base_url}/files", headers=conditional_headers)
    assert response.status_code == 200
    assert response.json()["capabilities"]["editable"] is False

    await anyio.to_thread.run_sync(_set_status, ConfigurationStatus.ARCHIVED)
    response = await async_client.get(f"{base_url}/files", headers=conditional_headers)
    assert response.status_code == 200
    assert response.json()["capabilities"]["editable"] is False
