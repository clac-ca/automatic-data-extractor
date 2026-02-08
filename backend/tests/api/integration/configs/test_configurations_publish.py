"""Configuration publish run behavior tests."""

from __future__ import annotations

import anyio
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ade_api.settings import Settings
from ade_db.models import Configuration, ConfigurationStatus, Run, RunOperation, RunStatus
from tests.api.integration.configs.helpers import auth_headers, config_path, create_from_template

pytestmark = pytest.mark.asyncio


async def test_publish_configuration_returns_queued_publish_run(
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
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers=headers,
        json={
            "configuration_id": record["id"],
            "options": {
                "operation": "publish",
            },
        },
    )
    assert response.status_code == 201, response.text

    payload = response.json()
    assert payload["operation"] == "publish"
    assert payload["status"] == "queued"
    assert payload["configuration_id"] == record["id"]
    assert payload["links"]["events_stream"].endswith(
        f"/api/v1/workspaces/{workspace_id}/runs/{payload['id']}/events/stream"
    )
    assert payload["links"]["events_download"].endswith(
        f"/api/v1/workspaces/{workspace_id}/runs/{payload['id']}/events/download"
    )

    stmt = select(Run).where(Run.id == payload["id"])

    def _load_run():
        return db_session.execute(stmt).scalar_one()

    run = await anyio.to_thread.run_sync(_load_run)
    assert run.operation is RunOperation.PUBLISH
    assert run.status is RunStatus.QUEUED


async def test_publish_reuses_existing_in_flight_run(
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

    publish_payload = {
        "configuration_id": record["id"],
        "options": {
            "operation": "publish",
        },
    }
    first = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers=headers,
        json=publish_payload,
    )
    second = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers=headers,
        json=publish_payload,
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]


async def test_publish_returns_409_when_configuration_not_draft(
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
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers=headers,
        json={
            "configuration_id": record["id"],
            "options": {
                "operation": "publish",
            },
        },
    )
    assert response.status_code == 409
    assert "draft" in (response.json().get("detail") or "").lower()


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
            'name = "ade_config"\n'
            'version = "0.1.0"\n'
            'dependencies = ["pandas"]\n'
        ),
        encoding="utf-8",
    )

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/runs",
        headers=headers,
        json={
            "configuration_id": record["id"],
            "options": {
                "operation": "publish",
            },
        },
    )
    assert response.status_code == 422, response.text
    payload = response.json()
    detail = payload.get("detail")
    if isinstance(detail, dict):
        assert detail.get("error") == "engine_dependency_missing"
    else:
        assert "ade-engine" in str(detail)
