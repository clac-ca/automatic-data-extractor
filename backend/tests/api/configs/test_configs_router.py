import base64
import io
import json
from typing import Any
from zipfile import ZipFile

import pytest
from httpx import AsyncClient

from backend.tests.utils import login

pytestmark = pytest.mark.asyncio


async def _auth(async_client: AsyncClient, identity: dict[str, Any]) -> tuple[dict[str, str], str]:
    owner = identity["workspace_owner"]
    token, _ = await login(
        async_client,
        email=owner["email"],  # type: ignore[index]
        password=owner["password"],  # type: ignore[index]
    )
    return {"Authorization": f"Bearer {token}"}, identity["workspace_id"]  # type: ignore[return-value]


def _package(manifest: dict[str, Any], name: str = "package") -> dict[str, str]:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("columns/example.py", "def detect(*_, **__):\n    return {}\n")
    payload = base64.b64encode(buffer.getvalue()).decode()
    return {"filename": f"{name}.zip", "content": payload}


async def test_config_version_lifecycle(async_client: AsyncClient, seed_identity: dict[str, Any]) -> None:
    headers, workspace_id = await _auth(async_client, seed_identity)
    base = f"/api/v1/workspaces/{workspace_id}/configs"

    manifest_v1 = {
        "target_fields": ["member_id", "name"],
        "engine": {"defaults": {"min_mapping_confidence": 0.5}},
    }
    created = await async_client.post(
        base,
        headers=headers,
        json={
            "slug": "people",
            "title": "People",
            "package": _package(manifest_v1, "people-v1"),
            "manifest": manifest_v1,
        },
    )
    assert created.status_code == 201, created.text
    config_detail = created.json()
    config_id = config_detail["config_id"]
    first_version = config_detail["versions"][0]

    manifest_v2 = {
        "target_fields": ["member_id", "name", "status"],
        "engine": {"defaults": {"min_mapping_confidence": 0.6}},
    }
    published = await async_client.post(
        f"{base}/{config_id}/versions",
        headers=headers,
        json={
            "label": "v2",
            "package": _package(manifest_v2, "people-v2"),
            "manifest": manifest_v2,
        },
    )
    assert published.status_code == 201, published.text
    second_version = published.json()

    versions = await async_client.get(
        f"{base}/{config_id}/versions",
        headers=headers,
    )
    assert versions.status_code == 200
    version_ids = {item["config_version_id"] for item in versions.json()}
    assert version_ids == {first_version["config_version_id"], second_version["config_version_id"]}

    activated = await async_client.post(
        f"{base}/{config_id}/versions/{second_version['config_version_id']}/activate",
        headers=headers,
    )
    assert activated.status_code == 200
    activated_payload = activated.json()
    assert activated_payload["active_version"]["config_version_id"] == second_version["config_version_id"]

    archived_version = await async_client.delete(
        f"{base}/{config_id}/versions/{first_version['config_version_id']}",
        headers=headers,
    )
    assert archived_version.status_code == 204

    archived_versions = await async_client.get(
        f"{base}/{config_id}/versions?include_deleted=true",
        headers=headers,
    )
    assert archived_versions.status_code == 200
    restored = await async_client.post(
        f"{base}/{config_id}/versions/{first_version['config_version_id']}/restore",
        headers=headers,
    )
    assert restored.status_code == 200
    restored_payload = restored.json()
    assert restored_payload["config_version_id"] == first_version["config_version_id"]

    archived_config = await async_client.delete(f"{base}/{config_id}", headers=headers)
    assert archived_config.status_code == 204

    restored_config = await async_client.post(
        f"{base}/{config_id}/restore",
        headers=headers,
    )
    assert restored_config.status_code == 200
    assert restored_config.json()["deleted_at"] is None


async def test_list_configs_includes_active_version(async_client: AsyncClient, seed_identity: dict[str, Any]) -> None:
    headers, workspace_id = await _auth(async_client, seed_identity)
    base = f"/api/v1/workspaces/{workspace_id}/configs"
    manifest = {"target_fields": ["code"]}
    await async_client.post(
        base,
        headers=headers,
        json={
            "slug": "codes",
            "title": "Codes",
            "package": _package(manifest, "codes"),
            "manifest": manifest,
        },
    )
    listing = await async_client.get(base, headers=headers)
    assert listing.status_code == 200
    configs = listing.json()
    assert configs
    for item in configs:
        active = item.get("active_version")
        assert active is None or "config_version_id" in active
