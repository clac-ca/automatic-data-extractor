"""Integration tests for configuration APIs."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from ade_api.db import generate_uuid7
from ade_api.db.session import get_sessionmaker
from ade_api.models import Configuration, ConfigurationStatus
from ade_api.settings import get_settings
from tests.utils import login

pytestmark = pytest.mark.asyncio


async def _auth_headers(
    client: AsyncClient,
    *,
    email: str,
    password: str,
) -> dict[str, str]:
    token, _ = await login(client, email=email, password=password)
    return {"Authorization": f"Bearer {token}"}


async def _create_from_template(
    client: AsyncClient,
    *,
    workspace_id: str,
    headers: dict[str, str],
    display_name: str = "Config A",
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations",
        headers=headers,
        json={
            "display_name": display_name,
            "source": {"type": "template"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _config_path(workspace_id: str, configuration_id: str) -> Path:
    return (
        Path(get_settings().configs_dir)
        / str(workspace_id)
        / "config_packages"
        / str(configuration_id)
    )


async def test_create_configuration_and_validate(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(async_client, email=owner["email"], password=owner["password"])

    record = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )

    config_path = _config_path(workspace_id, record["id"])
    assert config_path.exists()
    init_file = config_path / "src" / "ade_config" / "__init__.py"
    settings_file = config_path / "settings.toml"
    assert init_file.exists()
    assert settings_file.exists()

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/validate",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["issues"] == []
    assert payload["content_digest"].startswith("sha256:")


async def test_clone_configuration_creates_copy(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(async_client, email=owner["email"], password=owner["password"])

    source = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )

    clone_response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations",
        headers=headers,
        json={
            "display_name": "Cloned Config",
            "source": {"type": "clone", "configuration_id": source["id"]},
        },
    )
    assert clone_response.status_code == 201, clone_response.text
    clone = clone_response.json()
    assert clone["display_name"] == "Cloned Config"
    clone_path = _config_path(workspace_id, clone["id"])
    assert clone_path.exists()
    assert (clone_path / "src" / "ade_config" / "__init__.py").exists()


async def test_validate_reports_issues_when_package_missing(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(async_client, email=owner["email"], password=owner["password"])
    record = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )
    package_path = _config_path(workspace_id, record["id"]) / "src" / "ade_config" / "__init__.py"
    package_path.unlink()

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/validate",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["issues"], "Expected issues when package import is broken"
    assert payload.get("content_digest") is None


async def test_validate_missing_config_returns_not_found(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(async_client, email=owner["email"], password=owner["password"])
    random_id = str(generate_uuid7())

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{random_id}/validate",
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "configuration_not_found"


async def test_file_editor_endpoints(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(async_client, email=owner["email"], password=owner["password"])
    record = await _create_from_template(
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


async def test_editing_non_draft_rejected(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(async_client, email=owner["email"], password=owner["password"])
    record = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )
    base_url = f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}"
    await async_client.post(
        f"{base_url}/activate",
        headers=headers,
        json={},
    )
    put_headers = dict(headers)
    put_headers["If-None-Match"] = "*"
    put_headers["Content-Type"] = "application/octet-stream"
    resp = await async_client.put(
        f"{base_url}/files/assets/blocked.txt?parents=1",
        headers=put_headers,
        content=b"forbidden",
    )
    assert resp.status_code == 409


async def test_activate_configuration_sets_active_and_digest(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(async_client, email=owner["email"], password=owner["password"])
    record = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )

    publish = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/publish",
        headers=headers,
        json=None,
    )
    assert publish.status_code == 200, publish.text

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/activate",
        headers=headers,
        json={},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "active"
    assert payload["content_digest"].startswith("sha256:")

    settings = get_settings()
    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        stmt = select(Configuration).where(
            Configuration.workspace_id == workspace_id,
            Configuration.id == record["id"],
        )
        result = await session.execute(stmt)
        config = result.scalar_one()
        assert config.status == "active"
        assert config.content_digest == payload["content_digest"]


async def test_activate_demotes_previous_active(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(async_client, email=owner["email"], password=owner["password"])
    first = await _create_from_template(
        async_client, workspace_id=workspace_id, headers=headers, display_name="First"
    )
    await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{first['id']}/publish",
        headers=headers,
        json=None,
    )
    second = await _create_from_template(
        async_client, workspace_id=workspace_id, headers=headers, display_name="Second"
    )
    await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{second['id']}/publish",
        headers=headers,
        json=None,
    )

    await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{first['id']}/activate",
        headers=headers,
        json={},
    )
    await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{second['id']}/activate",
        headers=headers,
        json={},
    )

    settings = get_settings()
    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        stmt = select(Configuration).where(Configuration.workspace_id == workspace_id)
        result = await session.execute(stmt)
        configs = {str(row.id): row for row in result.scalars()}
        assert configs[str(first["id"])].status is ConfigurationStatus.INACTIVE
        assert configs[str(second["id"])].status is ConfigurationStatus.ACTIVE


async def test_activate_returns_422_when_validation_fails(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(async_client, email=owner["email"], password=owner["password"])
    record = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )
    package_path = _config_path(workspace_id, record["id"]) / "src" / "ade_config" / "__init__.py"
    package_path.unlink()

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/publish",
        headers=headers,
        json=None,
    )
    assert response.status_code == 422
    problem = response.json()
    detail = problem.get("detail") or {}
    assert detail.get("error") == "validation_failed"
    assert detail.get("issues")


async def test_deactivate_configuration_sets_inactive(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(async_client, email=owner["email"], password=owner["password"])
    record = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}/deactivate",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "inactive"


async def test_list_and_read_configurations(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(async_client, email=owner["email"], password=owner["password"])
    record = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )

    list_response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/configurations",
        headers=headers,
    )
    assert list_response.status_code == 200, list_response.text
    payload = list_response.json()
    items = payload["items"]
    assert any(item["id"] == record["id"] for item in items)

    detail_response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    payload = detail_response.json()
    assert payload["id"] == record["id"]
    assert payload["display_name"] == record["display_name"]
