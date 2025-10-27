"""Integration tests for the configs router."""

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


async def test_create_and_list_configs(async_client: AsyncClient, seed_identity: dict[str, object]) -> None:
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
    assert config_payload["draft"]["status"] == "draft"

    list_response = await async_client.get(f"{workspace_base}/configs", headers=headers)
    assert list_response.status_code == 200
    items = list_response.json()
    assert any(item["config_id"] == config_payload["config_id"] for item in items)


async def test_draft_file_etag_enforced(async_client: AsyncClient, seed_identity: dict[str, object]) -> None:
    headers, workspace_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    create_response = await async_client.post(
        f"{workspace_base}/configs",
        headers=headers,
        json={"slug": "draft-files", "title": "Draft Files"},
    )
    config_id = create_response.json()["config_id"]

    file_create = await async_client.post(
        f"{workspace_base}/configs/{config_id}/draft/files",
        headers=headers,
        json={"path": "columns/postal_code.py", "template": "def detect(value):\n    return value\n"},
    )
    assert file_create.status_code == 201, file_create.text

    file_detail = await async_client.get(
        f"{workspace_base}/configs/{config_id}/draft/files/columns/postal_code.py",
        headers=headers,
    )
    assert file_detail.status_code == 200
    etag = file_detail.headers.get("etag")
    assert etag

    bad_update = await async_client.put(
        f"{workspace_base}/configs/{config_id}/draft/files/columns/postal_code.py",
        headers={**headers, "If-Match": "bogus"},
        json={"code": "# overwrite"},
    )
    assert bad_update.status_code == 412

    good_update = await async_client.put(
        f"{workspace_base}/configs/{config_id}/draft/files/columns/postal_code.py",
        headers={**headers, "If-Match": etag},
        json={"code": "def detect(value):\n    return value.strip()\n"},
    )
    assert good_update.status_code == 200, good_update.text
    new_sha = good_update.json()["sha256"]
    assert new_sha != file_detail.json()["sha256"]


async def test_publish_flow(async_client: AsyncClient, seed_identity: dict[str, object]) -> None:
    headers, workspace_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    create_response = await async_client.post(
        f"{workspace_base}/configs",
        headers=headers,
        json={"slug": "publish", "title": "Publish Flow"},
    )
    assert create_response.status_code == 201
    config_id = create_response.json()["config_id"]

    await async_client.post(
        f"{workspace_base}/configs/{config_id}/draft/files",
        headers=headers,
        json={"path": "columns/value.py", "template": "def transform(value):\n    return value\n"},
    )

    manifest_patch = await async_client.patch(
        f"{workspace_base}/configs/{config_id}/draft/manifest",
        headers=headers,
        json={
            "manifest": {
                "columns": [
                    {
                        "key": "value",
                        "label": "Value",
                        "path": "columns/value.py",
                        "ordinal": 1,
                        "required": True,
                        "enabled": True,
                        "depends_on": [],
                    }
                ]
            }
        },
    )
    assert manifest_patch.status_code == 200, manifest_patch.text

    publish = await async_client.post(
        f"{workspace_base}/configs/{config_id}/publish",
        headers=headers,
        json={"semver": "1.0.0", "message": "Initial"},
    )
    assert publish.status_code == 201, publish.text

    detail = await async_client.get(
        f"{workspace_base}/configs/{config_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["published"] is not None
    assert payload["published"]["semver"] == "1.0.0"


async def test_publish_with_missing_file_returns_400(
    async_client: AsyncClient,
    seed_identity: dict[str, object],
) -> None:
    headers, workspace_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    create_response = await async_client.post(
        f"{workspace_base}/configs",
        headers=headers,
        json={"slug": "publish-missing", "title": "Publish Missing"},
    )
    assert create_response.status_code == 201
    config_id = create_response.json()["config_id"]

    await async_client.post(
        f"{workspace_base}/configs/{config_id}/draft/files",
        headers=headers,
        json={"path": "columns/value.py", "template": "def transform(value):\n    return value\n"},
    )

    manifest_patch = await async_client.patch(
        f"{workspace_base}/configs/{config_id}/draft/manifest",
        headers=headers,
        json={
            "manifest": {
                "columns": [
                    {
                        "key": "value",
                        "label": "Value",
                        "path": "columns/value.py",
                        "ordinal": 1,
                        "required": True,
                        "enabled": True,
                        "depends_on": [],
                    }
                ]
            }
        },
    )
    assert manifest_patch.status_code == 200

    delete_response = await async_client.delete(
        f"{workspace_base}/configs/{config_id}/draft/files/columns/value.py",
        headers=headers,
    )
    assert delete_response.status_code == 200

    publish = await async_client.post(
        f"{workspace_base}/configs/{config_id}/publish",
        headers=headers,
        json={"semver": "1.0.0", "message": "Initial"},
    )
    assert publish.status_code == 400


async def test_manifest_patch_missing_file_returns_400(
    async_client: AsyncClient,
    seed_identity: dict[str, object],
) -> None:
    headers, workspace_id = await _auth_headers(async_client, seed_identity)
    workspace_base = f"/api/v1/workspaces/{workspace_id}"

    create_response = await async_client.post(
        f"{workspace_base}/configs",
        headers=headers,
        json={"slug": "bad-manifest", "title": "Bad Manifest"},
    )
    config_id = create_response.json()["config_id"]

    response = await async_client.patch(
        f"{workspace_base}/configs/{config_id}/draft/manifest",
        headers=headers,
        json={
            "manifest": {
                "columns": [
                    {
                        "key": "missing",
                        "label": "Missing",
                        "path": "columns/missing.py",
                        "ordinal": 1,
                        "required": True,
                        "enabled": True,
                        "depends_on": [],
                    }
                ]
            }
        },
    )
    assert response.status_code == 400
