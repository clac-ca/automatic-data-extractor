"""Integration tests for configuration APIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import io
import zipfile

import pytest
from httpx import AsyncClient

from sqlalchemy import select

from apps.api.app.features.configs.models import Configuration
from apps.api.app.settings import get_settings
from apps.api.app.shared.db import generate_ulid
from apps.api.app.shared.db.session import get_sessionmaker
from apps.api.tests.utils import login

pytestmark = pytest.mark.asyncio

_settings = get_settings()
CSRF_COOKIE = _settings.session_csrf_cookie_name


async def _auth_headers(
    client: AsyncClient,
    *,
    email: str,
    password: str,
) -> dict[str, str]:
    await login(client, email=email, password=password)
    token = client.cookies.get(CSRF_COOKIE)
    assert token, "Missing CSRF cookie"
    return {"X-CSRF-Token": token}


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
            "source": {"type": "template", "template_id": "default"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _config_path(workspace_id: str, config_id: str) -> Path:
    return (
        Path(get_settings().configs_dir)
        / workspace_id
        / "config_packages"
        / config_id
    )


async def test_create_configuration_and_validate(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )

    record = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )

    config_path = _config_path(workspace_id, record["config_id"])
    assert config_path.exists()
    manifest = config_path / "src" / "ade_config" / "manifest.json"
    assert manifest.exists()

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['config_id']}/validate",
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
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )

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
            "source": {"type": "clone", "config_id": source["config_id"]},
        },
    )
    assert clone_response.status_code == 201, clone_response.text
    clone = clone_response.json()
    assert clone["display_name"] == "Cloned Config"
    clone_path = _config_path(workspace_id, clone["config_id"])
    assert clone_path.exists()
    assert (clone_path / "src" / "ade_config" / "manifest.json").exists()


async def test_validate_reports_issues_when_manifest_missing(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )
    record = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )
    manifest_path = (
        _config_path(workspace_id, record["config_id"])
        / "src"
        / "ade_config"
        / "manifest.json"
    )
    manifest_path.unlink()

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['config_id']}/validate",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["issues"], "Expected issues when manifest is missing"
    assert payload.get("content_digest") is None


async def test_create_missing_template_returns_not_found(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations",
        headers=headers,
        json={
            "display_name": "Bad Template",
            "source": {"type": "template", "template_id": "missing-template"},
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "source_not_found"


async def test_validate_missing_config_returns_not_found(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )
    random_id = generate_ulid()

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{random_id}/validate",
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "config_not_found"


async def test_file_editor_endpoints(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )
    record = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )
    base_url = f"/api/v1/workspaces/{workspace_id}/configurations/{record['config_id']}"

    resp = await async_client.get(f"{base_url}/files", headers=headers)
    assert resp.status_code == 200
    tree = resp.json()
    assert tree["entries"], "expected file listing to contain entries"

    create_headers = dict(headers)
    create_headers["If-None-Match"] = "*"
    create_headers["Content-Type"] = "application/octet-stream"
    resp = await async_client.put(
        f"{base_url}/files/assets/new.txt?parents=1",
        headers=create_headers,
        content=b"hello world",
    )
    assert resp.status_code == 201, resp.text
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

    resp = await async_client.post(
        f"{base_url}/directories/assets/new_folder",
        headers=headers,
    )
    assert resp.status_code == 201

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
        assert "src/ade_config/manifest.json" in archive.namelist()


async def test_editing_non_draft_rejected(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )
    record = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )
    base_url = f"/api/v1/workspaces/{workspace_id}/configurations/{record['config_id']}"
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
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )
    record = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['config_id']}/activate",
        headers=headers,
        json={},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "active"
    assert payload["config_version"] == 1
    assert payload["content_digest"].startswith("sha256:")

    settings = get_settings()
    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        stmt = select(Configuration).where(
            Configuration.workspace_id == workspace_id,
            Configuration.config_id == record["config_id"],
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
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )
    first = await _create_from_template(
        async_client, workspace_id=workspace_id, headers=headers, display_name="First"
    )
    second = await _create_from_template(
        async_client, workspace_id=workspace_id, headers=headers, display_name="Second"
    )

    await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{first['config_id']}/activate",
        headers=headers,
        json={},
    )
    await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{second['config_id']}/activate",
        headers=headers,
        json={},
    )

    settings = get_settings()
    session_factory = get_sessionmaker(settings=settings)
    async with session_factory() as session:
        stmt = select(Configuration).where(Configuration.workspace_id == workspace_id)
        result = await session.execute(stmt)
        configs = {row.config_id: row for row in result.scalars()}
        assert configs[first["config_id"]].status == "inactive"
        assert configs[second["config_id"]].status == "active"


async def test_activate_returns_422_when_validation_fails(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )
    record = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )
    manifest_path = (
        _config_path(workspace_id, record["config_id"])
        / "src"
        / "ade_config"
        / "manifest.json"
    )
    manifest_path.unlink()

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['config_id']}/activate",
        headers=headers,
        json={},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "validation_failed"
    assert detail["issues"]


async def test_deactivate_configuration_sets_inactive(
    async_client: AsyncClient,
    seed_identity: dict[str, Any],
) -> None:
    workspace_id = seed_identity["workspace_id"]
    owner = seed_identity["workspace_owner"]
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )
    record = await _create_from_template(
        async_client,
        workspace_id=workspace_id,
        headers=headers,
    )

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['config_id']}/deactivate",
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
    headers = await _auth_headers(
        async_client, email=owner["email"], password=owner["password"]
    )
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
    assert any(item["config_id"] == record["config_id"] for item in items)

    detail_response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/configurations/{record['config_id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    payload = detail_response.json()
    assert payload["config_id"] == record["config_id"]
    assert payload["display_name"] == record["display_name"]
