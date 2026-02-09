"""Configuration history, restore, and notes tests."""

from __future__ import annotations

import anyio
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from uuid import UUID

from ade_db.models import Configuration, ConfigurationStatus
from tests.api.integration.configs.helpers import auth_headers, config_path, create_from_template

pytestmark = pytest.mark.asyncio


async def test_workspace_history_lineage_scope_returns_same_family_only(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)

    root = await create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
        display_name="Root Config",
    )
    clone_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations",
        headers=headers,
        json={
            "display_name": "Child Draft",
            "source": {"type": "clone", "configuration_id": root["id"]},
            "notes": "Draft fork for tests",
        },
    )
    assert clone_response.status_code == 201, clone_response.text
    child = clone_response.json()

    unrelated = await create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
        display_name="Unrelated",
    )

    read_response = await async_client.get(
        (
            f"/api/v1/workspaces/{workspace_id}/configurations/{child['id']}"
            "/files/src/ade_config/__init__.py"
        ),
        headers={**headers, "Accept": "application/json"},
    )
    assert read_response.status_code == 200, read_response.text
    etag = read_response.json().get("etag")
    assert isinstance(etag, str) and etag

    write_response = await async_client.put(
        (
            f"/api/v1/workspaces/{workspace_id}/configurations/{child['id']}"
            "/files/src/ade_config/__init__.py?parents=true"
        ),
        headers={**headers, "Content-Type": "text/plain", "If-Match": etag},
        content="# history test\n",
    )
    assert write_response.status_code in {200, 201}, write_response.text

    history_response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/configurations/history",
        headers=headers,
        params={
            "focus_configuration_id": child["id"],
            "scope": "lineage",
            "status_filter": "all",
            "limit": 200,
        },
    )
    assert history_response.status_code == 200, history_response.text
    payload = history_response.json()
    ids = {item["id"] for item in payload["items"]}
    assert root["id"] in ids
    assert child["id"] in ids
    assert unrelated["id"] not in ids

    child_item = next(item for item in payload["items"] if item["id"] == child["id"])
    assert child_item["source_kind"] == "clone"
    assert child_item["source_configuration_id"] == root["id"]
    assert child_item["notes"] == "Draft fork for tests"
    assert child_item["changes_unavailable"] is False
    assert (child_item.get("changes") or {}).get("total", 0) >= 1


async def test_per_configuration_history_endpoint_is_not_exposed(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)
    config = await create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
        display_name="No Per-config History",
    )

    response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/configurations/{config['id']}/history",
        headers=headers,
    )
    assert response.status_code == 404


async def test_workspace_history_endpoint_supports_workspace_and_lineage_scopes(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)

    root = await create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
        display_name="Scope Root",
    )
    clone_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations",
        headers=headers,
        json={
            "display_name": "Scope Child",
            "source": {"type": "clone", "configuration_id": root["id"]},
        },
    )
    assert clone_response.status_code == 201, clone_response.text
    child = clone_response.json()
    unrelated = await create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
        display_name="Scope Unrelated",
    )

    workspace_history_response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/configurations/history",
        headers=headers,
        params={
            "focus_configuration_id": child["id"],
            "scope": "workspace",
            "status_filter": "all",
            "limit": 200,
        },
    )
    assert workspace_history_response.status_code == 200, workspace_history_response.text
    workspace_payload = workspace_history_response.json()
    workspace_ids = {item["id"] for item in workspace_payload["items"]}
    assert root["id"] in workspace_ids
    assert child["id"] in workspace_ids
    assert unrelated["id"] in workspace_ids
    assert workspace_payload["current_configuration_id"] == child["id"]
    assert workspace_payload["focus_configuration_id"] == child["id"]

    lineage_history_response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/configurations/history",
        headers=headers,
        params={
            "focus_configuration_id": child["id"],
            "scope": "lineage",
            "status_filter": "all",
            "limit": 200,
        },
    )
    assert lineage_history_response.status_code == 200, lineage_history_response.text
    lineage_payload = lineage_history_response.json()
    lineage_ids = {item["id"] for item in lineage_payload["items"]}
    assert root["id"] in lineage_ids
    assert child["id"] in lineage_ids
    assert unrelated["id"] not in lineage_ids


async def test_restore_creates_new_draft_with_restore_metadata(
    async_client: AsyncClient,
    seed_identity,
    settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)

    source = await create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
        display_name="Published-ish",
    )

    restore_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{source['id']}/restore",
        headers=headers,
        json={
            "source_configuration_id": source["id"],
            "display_name": "Restored Draft",
            "notes": "Rolled back after mapping regression",
        },
    )
    assert restore_response.status_code == 201, restore_response.text
    restored = restore_response.json()
    assert restored["status"] == "draft"
    assert restored["source_kind"] == "restore"
    assert restored["source_configuration_id"] == source["id"]
    assert restored["notes"] == "Rolled back after mapping regression"

    restored_path = config_path(settings, workspace_id, restored["id"])
    assert restored_path.exists()


async def test_configuration_patch_requires_draft_status(
    async_client: AsyncClient,
    seed_identity,
    db_session,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)
    config = await create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
        display_name="Notes Config",
    )

    update_response = await async_client.patch(
        f"/api/v1/workspaces/{workspace_id}/configurations/{config['id']}",
        headers=headers,
        json={"notes": "Initial note"},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["notes"] == "Initial note"

    stmt = select(Configuration).where(Configuration.id == UUID(config["id"]))

    def _promote_to_active() -> None:
        record = db_session.execute(stmt).scalar_one()
        record.status = ConfigurationStatus.ACTIVE
        db_session.commit()

    await anyio.to_thread.run_sync(_promote_to_active)

    blocked_response = await async_client.patch(
        f"/api/v1/workspaces/{workspace_id}/configurations/{config['id']}",
        headers=headers,
        json={"notes": "Should fail"},
    )
    assert blocked_response.status_code == 409
    assert "editable" in (blocked_response.json().get("detail") or "").lower()


async def test_notes_patch_endpoint_is_not_exposed(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)
    config = await create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
        display_name="No Notes Endpoint",
    )

    response = await async_client.patch(
        f"/api/v1/workspaces/{workspace_id}/configurations/{config['id']}/notes",
        headers=headers,
        json={"notes": "should fail"},
    )
    assert response.status_code == 404
