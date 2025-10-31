"""Integration tests for the file-backed configs router."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.tests.utils import login


pytestmark = pytest.mark.asyncio


async def _auth_headers(async_client: AsyncClient, identity: dict[str, object]) -> tuple[dict[str, str], str]:
    """Authenticate as the workspace owner and return headers + workspace id."""

    owner = identity["workspace_owner"]
    token, _ = await login(
        async_client,
        email=owner["email"],  # type: ignore[index]
        password=owner["password"],  # type: ignore[index]
    )
    workspace_id = identity["workspace_id"]
    csrf_token = async_client.cookies.get("backend_app_csrf")
    headers = {"Authorization": f"Bearer {token}"}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return headers, workspace_id  # type: ignore[return-value]


async def test_config_lifecycle(async_client: AsyncClient, seed_identity: dict[str, object]) -> None:
    """End-to-end lifecycle covering manifest edits and activation."""

    headers, workspace_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"
    collection_url = f"{workspace_base}/configs/"

    create_response = await async_client.post(
        collection_url,
        headers=headers,
        json={"title": "Lifecycle Config"},
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    config_id = created["config_id"]
    assert created["status"] == "inactive"

    list_response = await async_client.get(collection_url, headers=headers)
    assert list_response.status_code == 200
    config_ids = {item["config_id"] for item in list_response.json()}
    assert config_id in config_ids

    manifest_response = await async_client.get(
        f"{workspace_base}/configs/{config_id}/manifest",
        headers=headers,
    )
    assert manifest_response.status_code == 200, manifest_response.text
    manifest = manifest_response.json()
    assert manifest["info"]["schema"] == "ade.manifest/v0.5"
    manifest["env"]["DEFAULT_CURRENCY"] = "CAD"

    put_response = await async_client.put(
        f"{workspace_base}/configs/{config_id}/manifest",
        headers=headers,
        json=manifest,
    )
    assert put_response.status_code == 200, put_response.text
    updated_manifest = put_response.json()
    assert updated_manifest["env"]["DEFAULT_CURRENCY"] == "CAD"

    files_response = await async_client.get(
        f"{workspace_base}/configs/{config_id}/files",
        headers=headers,
    )
    assert files_response.status_code == 200, files_response.text
    files = files_response.json()
    paths = {item["path"] for item in files}
    assert "manifest.json" in paths
    assert "columns/member_id.py" in paths

    read_response = await async_client.get(
        f"{workspace_base}/configs/{config_id}/files/manifest.json",
        headers=headers,
    )
    assert read_response.status_code == 200
    assert "DEFAULT_CURRENCY" in read_response.text

    validate_response = await async_client.post(
        f"{workspace_base}/configs/{config_id}/validate",
        headers=headers,
    )
    assert validate_response.status_code == 200, validate_response.text
    validation_payload = validate_response.json()
    assert validation_payload["manifest"]["info"]["title"] == "Example Membership Config"
    assert validation_payload["issues"] == []

    activate_response = await async_client.post(
        f"{workspace_base}/configs/{config_id}/activate",
        headers=headers,
    )
    assert activate_response.status_code == 200, activate_response.text
    activated = activate_response.json()
    assert activated["status"] == "active"

    active_lookup = await async_client.get(
        f"{workspace_base}/configs/active",
        headers=headers,
    )
    assert active_lookup.status_code == 200
    assert active_lookup.json()["config_id"] == config_id

    conflict_update = await async_client.put(
        f"{workspace_base}/configs/{config_id}/manifest",
        headers=headers,
        json=manifest,
    )
    assert conflict_update.status_code == 409


async def test_clone_archive_and_delete(async_client: AsyncClient, seed_identity: dict[str, object]) -> None:
    """Cloning produces a new bundle that can be archived and removed."""

    headers, workspace_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"
    collection_url = f"{workspace_base}/configs/"

    create_response = await async_client.post(
        collection_url,
        headers=headers,
        json={"title": "Source Config"},
    )
    create_response.raise_for_status()
    source_id = create_response.json()["config_id"]

    clone_response = await async_client.post(
        f"{workspace_base}/configs/{source_id}/clone",
        headers=headers,
        json={"title": "Cloned Config"},
    )
    assert clone_response.status_code == 201, clone_response.text
    clone_id = clone_response.json()["config_id"]

    archive_response = await async_client.patch(
        f"{workspace_base}/configs/{clone_id}",
        headers=headers,
        json={"status": "archived"},
    )
    assert archive_response.status_code == 200, archive_response.text
    assert archive_response.json()["status"] == "archived"

    delete_response = await async_client.delete(
        f"{workspace_base}/configs/{clone_id}",
        headers=headers,
    )
    assert delete_response.status_code == 204, delete_response.text

    list_response = await async_client.get(collection_url, headers=headers)
    remaining_ids = {item["config_id"] for item in list_response.json()}
    assert clone_id not in remaining_ids

