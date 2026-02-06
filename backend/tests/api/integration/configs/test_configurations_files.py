"""Configuration file editor endpoint tests."""

from __future__ import annotations

import io
import zipfile

import pytest
from httpx import AsyncClient

from tests.api.integration.configs.helpers import auth_headers, create_from_template

pytestmark = pytest.mark.asyncio


async def test_file_editor_endpoints(
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
    base_url = f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}"

    resp = await async_client.get(f"{base_url}/files", headers=headers)
    assert resp.status_code == 200
    tree = resp.json()
    assert tree["entries"], "expected file listing to contain entries"
    dir_entries = [entry for entry in tree["entries"] if entry["kind"] == "dir"]
    assert all(not entry["path"].endswith("/") for entry in dir_entries)
    paths = {entry["path"]: entry for entry in tree["entries"]}
    assert "src" in paths
    assert paths["src"]["parent"] == ""
    assert paths["src"]["kind"] == "dir"
    assert "src/ade_config" in paths
    assert paths["src/ade_config"]["parent"] == "src"
    assert paths["src/ade_config"]["kind"] == "dir"

    create_headers = dict(headers)
    create_headers["If-None-Match"] = "*"
    create_headers["Content-Type"] = "application/octet-stream"
    resp = await async_client.put(
        f"{base_url}/files/assets/new.txt?parents=1",
        headers=create_headers,
        content=b"hello world",
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["created"] is True
    assert body["path"] == "assets/new.txt"
    assert resp.headers.get("Location", "").endswith("/files/assets/new.txt")
    etag = resp.headers.get("ETag")

    resp = await async_client.get(
        f"{base_url}/files/assets/new.txt",
        headers=headers,
        params={"format": "json"},
    )
    assert resp.status_code == 200
    json_body = resp.json()
    assert json_body["encoding"] == "utf-8"

    update_headers = dict(headers)
    update_headers["If-Match"] = etag
    update_headers["Content-Type"] = "application/octet-stream"
    resp = await async_client.put(
        f"{base_url}/files/assets/new.txt",
        headers=update_headers,
        content=b"updated",
    )
    assert resp.status_code == 200
    updated_body = resp.json()
    assert updated_body["created"] is False
    assert "Location" not in resp.headers
    new_etag = resp.headers.get("ETag")

    resp = await async_client.get(
        f"{base_url}/files/assets/new.txt",
        headers=headers,
    )
    assert resp.content == b"updated"

    delete_headers = dict(headers)
    delete_headers["If-Match"] = new_etag
    resp = await async_client.delete(
        f"{base_url}/files/assets/new.txt",
        headers=delete_headers,
    )
    assert resp.status_code == 204

    resp = await async_client.put(
        f"{base_url}/directories/assets/new_folder",
        headers=headers,
    )
    assert resp.status_code == 201
    dir_body = resp.json()
    assert dir_body["created"] is True
    assert dir_body["path"] == "assets/new_folder"
    assert resp.headers.get("Location", "").endswith("/directories/assets/new_folder")

    resp = await async_client.put(
        f"{base_url}/directories/assets/new_folder",
        headers=headers,
    )
    assert resp.status_code == 200
    dir_existing = resp.json()
    assert dir_existing["created"] is False
    assert dir_existing["path"] == "assets/new_folder"
    assert "Location" not in resp.headers

    resp = await async_client.delete(
        f"{base_url}/directories/assets/new_folder",
        headers=headers,
        params={"recursive": "1"},
    )
    assert resp.status_code == 204

    resp = await async_client.get(
        f"{base_url}/export",
        headers=headers,
    )
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
        assert "src/ade_config/__init__.py" in archive.namelist()
