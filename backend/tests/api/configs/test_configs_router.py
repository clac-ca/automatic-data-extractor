"""Integration tests for the configs router (activation workflow)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.tests.utils import login


pytestmark = pytest.mark.asyncio


async def _auth_headers(async_client: AsyncClient, identity: dict[str, object]) -> tuple[dict[str, str], str]:
    owner = identity["workspace_owner"]
    token, _ = await login(
        async_client,
        email=owner["email"],  # type: ignore[index]
        password=owner["password"],  # type: ignore[index]
    )
    workspace_id = identity["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers, workspace_id  # type: ignore[return-value]


async def test_create_list_configs(async_client: AsyncClient, seed_identity: dict[str, object]) -> None:
    headers, workspace_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    create_response = await async_client.post(
        f"{workspace_base}/configs",
        headers=headers,
        json={"slug": "alpha", "title": "Alpha Config"},
    )
    assert create_response.status_code == 201, create_response.text
    config_payload = create_response.json()
    assert config_payload["slug"] == "alpha"
    assert config_payload["active_version"] is not None

    list_response = await async_client.get(f"{workspace_base}/configs", headers=headers)
    assert list_response.status_code == 200
    items = list_response.json()
    assert any(item["config_id"] == config_payload["config_id"] for item in items)


async def test_version_activation_flow(async_client: AsyncClient, seed_identity: dict[str, object]) -> None:
    headers, workspace_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    config_response = await async_client.post(
        f"{workspace_base}/configs",
        headers=headers,
        json={"slug": "activation-flow", "title": "Activation Flow"},
    )
    config_response.raise_for_status()
    config = config_response.json()
    config_id = config["config_id"]

    version_response = await async_client.post(
        f"{workspace_base}/configs/{config_id}/versions",
        headers=headers,
        json={"semver": "1.0.0", "seed_defaults": True},
    )
    assert version_response.status_code == 201, version_response.text
    version = version_response.json()
    version_id = version["config_version_id"]

    file_response = await async_client.post(
        f"{workspace_base}/configs/{config_id}/versions/{version_id}/scripts",
        headers=headers,
        json={"path": "columns/value.py", "template": "def transform(value):\n    return value\n"},
    )
    assert file_response.status_code == 201, file_response.text
    file_etag = file_response.headers["etag"]

    # ETag guard should block updates without a matching hash
    bad_update = await async_client.put(
        f"{workspace_base}/configs/{config_id}/versions/{version_id}/scripts/columns/value.py",
        headers={**headers, "If-Match": "\"bogus\""},
        json={"code": "# overwrite"},
    )
    assert bad_update.status_code == 412

    good_update = await async_client.put(
        f"{workspace_base}/configs/{config_id}/versions/{version_id}/scripts/columns/value.py",
        headers={**headers, "If-Match": file_etag},
        json={"code": "def transform(value):\n    return value.strip()\n"},
    )
    assert good_update.status_code == 200
    file_etag = good_update.headers["etag"]

    manifest_response = await async_client.get(
        f"{workspace_base}/configs/{config_id}/versions/{version_id}/manifest",
        headers=headers,
    )
    assert manifest_response.status_code == 200, manifest_response.text
    manifest_payload = manifest_response.json()["manifest"]
    manifest_payload.setdefault("columns", []).append(
        {
            "key": "value",
            "label": "Value",
            "path": "columns/value.py",
            "ordinal": 1,
            "required": True,
            "enabled": True,
            "depends_on": [],
        }
    )
    etag = manifest_response.headers["etag"]

    manifest_patch = await async_client.patch(
        f"{workspace_base}/configs/{config_id}/versions/{version_id}/manifest",
        headers={**headers, "If-Match": etag},
        json={"manifest": manifest_payload},
    )
    assert manifest_patch.status_code == 200, manifest_patch.text

    validation = await async_client.post(
        f"{workspace_base}/configs/{config_id}/versions/{version_id}/validate",
        headers=headers,
    )
    assert validation.status_code == 200
    assert validation.json()["ready"] is True

    activate = await async_client.post(
        f"{workspace_base}/configs/{config_id}/versions/{version_id}/activate",
        headers=headers,
    )
    assert activate.status_code == 200, activate.text
    assert activate.json()["status"] == "active"

    detail = await async_client.get(
        f"{workspace_base}/configs/{config_id}",
        headers=headers,
    )
    detail.raise_for_status()
    payload = detail.json()
    assert payload["active_version"]["config_version_id"] == version_id

    # ETag captured earlier is no longer used after activation; updates should occur prior to activating


async def test_manifest_patch_requires_etag(async_client: AsyncClient, seed_identity: dict[str, object]) -> None:
    headers, workspace_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    config_response = await async_client.post(
        f"{workspace_base}/configs",
        headers=headers,
        json={"slug": "manifest-guard", "title": "Manifest Guard"},
    )
    config_id = config_response.json()["config_id"]

    version_response = await async_client.post(
        f"{workspace_base}/configs/{config_id}/versions",
        headers=headers,
        json={"semver": "test", "seed_defaults": True},
    )
    version_id = version_response.json()["config_version_id"]

    manifest_response = await async_client.get(
        f"{workspace_base}/configs/{config_id}/versions/{version_id}/manifest",
        headers=headers,
    )
    etag = manifest_response.headers["etag"]

    manifest_payload = manifest_response.json()["manifest"]
    manifest_payload["notes"] = "first"

    ok_patch = await async_client.patch(
        f"{workspace_base}/configs/{config_id}/versions/{version_id}/manifest",
        headers={**headers, "If-Match": etag},
        json={"manifest": manifest_payload},
    )
    assert ok_patch.status_code == 200
    new_etag = ok_patch.headers["etag"]

    stale_patch = await async_client.patch(
        f"{workspace_base}/configs/{config_id}/versions/{version_id}/manifest",
        headers={**headers, "If-Match": etag},
        json={"manifest": {"notes": "stale"}},
    )
    assert stale_patch.status_code == 412

    missing_header = await async_client.patch(
        f"{workspace_base}/configs/{config_id}/versions/{version_id}/manifest",
        headers=headers,
        json={"manifest": {"notes": "missing"}},
    )
    assert missing_header.status_code == 428

    # Use the latest ETag to ensure success
    final_patch = await async_client.patch(
        f"{workspace_base}/configs/{config_id}/versions/{version_id}/manifest",
        headers={**headers, "If-Match": new_etag},
        json={"manifest": {"notes": "ok"}},
    )
    assert final_patch.status_code == 200


async def test_archive_restore_config(async_client: AsyncClient, seed_identity: dict[str, object]) -> None:
    headers, workspace_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    create_response = await async_client.post(
        f"{workspace_base}/configs",
        headers=headers,
        json={"slug": "archivable", "title": "Archivable"},
    )
    config_id = create_response.json()["config_id"]

    archive_response = await async_client.delete(
        f"{workspace_base}/configs/{config_id}",
        headers=headers,
    )
    assert archive_response.status_code == 204

    active_list = await async_client.get(f"{workspace_base}/configs", headers=headers)
    assert all(item["config_id"] != config_id for item in active_list.json())

    archived_list = await async_client.get(
        f"{workspace_base}/configs?include_deleted=true",
        headers=headers,
    )
    archived_item = next(item for item in archived_list.json() if item["config_id"] == config_id)
    assert archived_item["deleted_at"] is not None

    restore_response = await async_client.post(
        f"{workspace_base}/configs/{config_id}/restore",
        headers=headers,
    )
    assert restore_response.status_code == 200

    active_again = await async_client.get(f"{workspace_base}/configs", headers=headers)
    assert any(item["config_id"] == config_id for item in active_again.json())


async def test_archive_and_restore_version(async_client: AsyncClient, seed_identity: dict[str, object]) -> None:
    headers, workspace_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    config_response = await async_client.post(
        f"{workspace_base}/configs",
        headers=headers,
        json={"slug": "version-archive", "title": "Version Archive"},
    )
    config_id = config_response.json()["config_id"]

    version_response = await async_client.post(
        f"{workspace_base}/configs/{config_id}/versions",
        headers=headers,
        json={"semver": "draft", "seed_defaults": True},
    )
    version_id = version_response.json()["config_version_id"]

    archive_version = await async_client.delete(
        f"{workspace_base}/configs/{config_id}/versions/{version_id}",
        headers=headers,
    )
    assert archive_version.status_code == 204

    versions = await async_client.get(
        f"{workspace_base}/configs/{config_id}/versions",
        headers=headers,
    )
    assert all(item["config_version_id"] != version_id for item in versions.json())

    archived_versions = await async_client.get(
        f"{workspace_base}/configs/{config_id}/versions?include_deleted=true",
        headers=headers,
    )
    archived = next(item for item in archived_versions.json() if item["config_version_id"] == version_id)
    assert archived["deleted_at"] is not None

    restore_version = await async_client.post(
        f"{workspace_base}/configs/{config_id}/versions/{version_id}/restore",
        headers=headers,
    )
    assert restore_version.status_code == 200

    versions_again = await async_client.get(
        f"{workspace_base}/configs/{config_id}/versions",
        headers=headers,
    )
    assert any(item["config_version_id"] == version_id for item in versions_again.json())
