import io
import json
from typing import Any
from uuid import uuid4
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


def _manifest(title: str, fields: list[str]) -> dict[str, Any]:
    return {
        "config_script_api_version": "1",
        "info": {
            "schema": "ade.manifest/v1.0",
            "title": title,
            "version": "1.0.0",
        },
        "engine": {
            "defaults": {
                "timeout_ms": 120000,
                "memory_mb": 256,
                "runtime_network_access": False,
                "mapping_score_threshold": 0.0,
            },
            "writer": {
                "mode": "row_streaming",
                "append_unmapped_columns": True,
                "unmapped_prefix": "raw_",
                "output_sheet": "Normalized",
            },
        },
        "env": {},
        "hooks": {
            "on_activate": [],
            "on_job_start": [],
            "on_after_extract": [],
            "on_job_end": [],
        },
        "columns": {
            "order": fields,
            "meta": {
                field: {
                    "label": field.replace("_", " ").title(),
                    "required": True,
                    "enabled": True,
                    "script": f"columns/{field}.py",
                }
                for field in fields
            },
        },
    }


def _package(manifest: dict[str, Any], name: str = "package") -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        archive.writestr("columns/__init__.py", "")
        for field in manifest["columns"]["order"]:
            script = f"columns/{field}.py"
            archive.writestr(
                script,
                (
                    "def detect_primary(*, header, values_sample, column_index, table, job_context, env):\n"
                    f"    return {{'scores': {{'{field}': 1.0}}}}\n\n"
                    "def transform(*, header, values, column_index, table, job_context, env):\n"
                    "    return {'values': list(values), 'warnings': []}\n"
                ),
            )
    return buffer.getvalue()


async def _post_config(
    async_client: AsyncClient,
    *,
    base: str,
    headers: dict[str, str],
    slug: str,
    title: str,
    manifest: dict[str, Any],
    package_name: str,
) -> Any:
    package_bytes = _package(manifest, package_name)
    response = await async_client.post(
        base,
        headers=headers,
        data={
            "slug": slug,
            "title": title,
            "manifest_json": json.dumps(manifest),
        },
        files={
            "package": (f"{package_name}.zip", package_bytes, "application/zip"),
        },
    )
    return response


async def test_config_version_lifecycle(async_client: AsyncClient, seed_identity: dict[str, Any]) -> None:
    headers, workspace_id = await _auth(async_client, seed_identity)
    base = f"/api/v1/workspaces/{workspace_id}/configs"

    manifest_v1 = _manifest("People", ["member_id", "name"])
    created = await _post_config(
        async_client,
        base=base,
        headers=headers,
        slug="people",
        title="People",
        manifest=manifest_v1,
        package_name="people-v1",
    )
    assert created.status_code == 201, created.text
    config_detail = created.json()
    config_id = config_detail["config_id"]
    first_version = config_detail["versions"][0]
    assert first_version["config_script_api_version"] == "1"

    manifest_v2 = _manifest("People", ["member_id", "name", "status"])
    package_bytes_v2 = _package(manifest_v2, "people-v2")
    published = await async_client.post(
        f"{base}/{config_id}/versions",
        headers=headers,
        data={
            "label": "v2",
            "manifest_json": json.dumps(manifest_v2),
        },
        files={
            "package": ("people-v2.zip", package_bytes_v2, "application/zip"),
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
    manifest = _manifest("Codes", ["code"])
    await _post_config(
        async_client,
        base=base,
        headers=headers,
        slug="codes",
        title="Codes",
        manifest=manifest,
        package_name="codes",
    )
    listing = await async_client.get(base, headers=headers)
    assert listing.status_code == 200
    configs = listing.json()
    assert configs
    for item in configs:
        active = item.get("active_version")
        assert active is None or "config_version_id" in active


async def test_config_draft_file_editing_flow(async_client: AsyncClient, seed_identity: dict[str, Any]) -> None:
    headers, workspace_id = await _auth(async_client, seed_identity)
    base = f"/api/v1/workspaces/{workspace_id}/configs"

    manifest = _manifest("Drafts", ["member_id", "first_name"])
    slug = f"draft-{uuid4().hex[:8]}"
    created = await _post_config(
        async_client,
        base=base,
        headers=headers,
        slug=slug,
        title="Draft Config",
        manifest=manifest,
        package_name="draft-base",
    )
    assert created.status_code == 201, created.text
    config_detail = created.json()
    config_id = config_detail["config_id"]
    base_version_id = config_detail["versions"][0]["config_version_id"]

    draft_create = await async_client.post(
        f"{base}/{config_id}/drafts",
        headers=headers,
        json={"base_config_version_id": base_version_id},
    )
    assert draft_create.status_code == 201, draft_create.text
    draft_id = draft_create.json()["draft_id"]

    drafts_listing = await async_client.get(f"{base}/{config_id}/drafts", headers=headers)
    assert drafts_listing.status_code == 200
    assert any(item["draft_id"] == draft_id for item in drafts_listing.json())

    files_response = await async_client.get(
        f"{base}/{config_id}/drafts/{draft_id}/files",
        headers=headers,
    )
    assert files_response.status_code == 200
    files_payload = files_response.json()
    assert any(entry["path"] == "manifest.json" for entry in files_payload)

    manifest_contents = await async_client.get(
        f"{base}/{config_id}/drafts/{draft_id}/files/manifest.json",
        headers=headers,
    )
    assert manifest_contents.status_code == 200
    manifest_file = manifest_contents.json()
    original_sha = manifest_file["sha256"]
    manifest_data = json.loads(manifest_file["content"])
    manifest_data["info"]["title"] = "Draft Config Updated"
    updated_manifest = json.dumps(manifest_data, indent=2)

    update_response = await async_client.put(
        f"{base}/{config_id}/drafts/{draft_id}/files/manifest.json",
        headers=headers,
        json={
            "content": updated_manifest,
            "encoding": "utf-8",
            "expected_sha256": original_sha,
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated_file = update_response.json()
    assert updated_file["sha256"] != original_sha

    conflict = await async_client.put(
        f"{base}/{config_id}/drafts/{draft_id}/files/manifest.json",
        headers=headers,
        json={
            "content": updated_manifest,
            "encoding": "utf-8",
            "expected_sha256": original_sha,
        },
    )
    assert conflict.status_code == 409

    publish_response = await async_client.post(
        f"{base}/{config_id}/drafts/{draft_id}/publish",
        headers=headers,
        json={"label": "draft-v2"},
    )
    assert publish_response.status_code == 201, publish_response.text
    published_version = publish_response.json()
    assert published_version["label"] == "draft-v2"

    versions_after = await async_client.get(f"{base}/{config_id}/versions", headers=headers)
    assert versions_after.status_code == 200
    assert len(versions_after.json()) == 2

    download_response = await async_client.get(
        f"{base}/{config_id}/drafts/{draft_id}/download",
        headers=headers,
    )
    assert download_response.status_code == 200
    with ZipFile(io.BytesIO(download_response.content)) as archive:
        assert "manifest.json" in archive.namelist()

    delete_response = await async_client.delete(
        f"{base}/{config_id}/drafts/{draft_id}",
        headers=headers,
    )
    assert delete_response.status_code == 204
