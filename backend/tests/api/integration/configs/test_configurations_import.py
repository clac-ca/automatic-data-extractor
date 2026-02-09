"""Configuration import endpoint tests."""

from __future__ import annotations

import io
import zipfile

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

import ade_api.features.configs.service as config_service_module
from ade_api.features.configs.exceptions import ConfigImportError
from ade_api.settings import Settings
from ade_db.models import Configuration
from tests.api.integration.configs.helpers import auth_headers, config_path, create_from_template

pytestmark = pytest.mark.asyncio


def _build_import_archive(
    *,
    wrapper: str = "ade-config-main",
    extra_files: dict[str, bytes] | None = None,
) -> bytes:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            f"{wrapper}/pyproject.toml",
            (
                "[project]\n"
                "name = \"ade_config\"\n"
                "version = \"0.1.0\"\n"
                "dependencies = [\"ade-engine\"]\n"
            ),
        )
        zf.writestr(f"{wrapper}/src/ade_config/__init__.py", "__all__ = []\n")
        for path, data in (extra_files or {}).items():
            zf.writestr(f"{wrapper}/{path}", data)
    return archive_bytes.getvalue()


async def test_import_configuration_from_wrapped_archive(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)

    archive = _build_import_archive()

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/import",
        headers=headers,
        data={"display_name": "Imported config", "notes": "from wrapped archive"},
        files={
            "file": ("config.zip", archive, "application/zip"),
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["source_kind"] == "import"

    root = config_path(settings, workspace_id, payload["id"])
    assert (root / "pyproject.toml").is_file()
    assert (root / "src" / "ade_config" / "__init__.py").is_file()
    assert not (root / "ade-config-main").exists()


async def test_import_configuration_allows_large_non_source_file_under_default_limit(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)

    archive = _build_import_archive(extra_files={"logs/engine_events.ndjson": b"x" * (600 * 1024)})

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/import",
        headers=headers,
        data={"display_name": "Imported config"},
        files={
            "file": ("config.zip", archive, "application/zip"),
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()

    root = config_path(settings, workspace_id, payload["id"])
    assert (root / "logs" / "engine_events.ndjson").is_file()


async def test_import_configuration_uses_configured_limit(
    async_client: AsyncClient,
    seed_identity,
    override_app_settings,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)

    archive = _build_import_archive(extra_files={"logs/too_big.ndjson": b"x" * 4096})

    override_app_settings(config_import_max_bytes=2048)

    blocked = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/import",
        headers=headers,
        data={"display_name": "Blocked import"},
        files={
            "file": ("config.zip", archive, "application/zip"),
        },
    )
    assert blocked.status_code == 400, blocked.text
    blocked_payload = blocked.json()
    assert blocked_payload.get("detail") == {
        "error": "file_too_large",
        "limit": 2048,
        "detail": "logs/too_big.ndjson",
    }
    assert blocked_payload.get("errors", [{}])[0].get("code") == "file_too_large"

    override_app_settings(config_import_max_bytes=8192)

    allowed = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/import",
        headers=headers,
        data={"display_name": "Allowed import"},
        files={
            "file": ("config.zip", archive, "application/zip"),
        },
    )
    assert allowed.status_code == 201, allowed.text


async def test_import_configuration_cleans_files_when_db_flush_fails(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)
    display_name = "Import flush failure"
    archive = _build_import_archive()
    workspace_root = config_path(settings, workspace_id, "placeholder").parent
    before_entries = (
        {path.name for path in workspace_root.iterdir() if path.is_dir()}
        if workspace_root.exists()
        else set()
    )

    original_flush = Session.flush

    def _flush_with_failure(self: Session, *args, **kwargs) -> None:
        if any(
            isinstance(item, Configuration) and item.display_name == display_name
            for item in self.new
        ):
            raise RuntimeError("forced_flush_failure")
        return original_flush(self, *args, **kwargs)

    monkeypatch.setattr(Session, "flush", _flush_with_failure)

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/import",
        headers=headers,
        data={"display_name": display_name},
        files={
            "file": ("config.zip", archive, "application/zip"),
        },
    )
    assert response.status_code == 500, response.text

    after_entries = (
        {path.name for path in workspace_root.iterdir() if path.is_dir()}
        if workspace_root.exists()
        else set()
    )
    assert after_entries == before_entries
    assert not any(name.startswith(".import-") for name in after_entries)


async def test_import_configuration_from_github_url(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)
    archive = _build_import_archive()

    monkeypatch.setattr(
        config_service_module,
        "download_github_archive",
        lambda *args, **kwargs: archive,
    )

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/import/github",
        headers=headers,
        json={
            "display_name": "GitHub import",
            "url": "https://github.com/octo/repo",
            "notes": "imported from github",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["source_kind"] == "import"

    root = config_path(settings, workspace_id, payload["id"])
    assert (root / "pyproject.toml").is_file()
    assert (root / "src" / "ade_config" / "__init__.py").is_file()


async def test_replace_configuration_from_github_url(
    async_client: AsyncClient,
    seed_identity,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)
    config = await create_from_template(
        async_client,
        workspace_id=str(workspace_id),
        headers=headers,
    )

    archive = _build_import_archive(wrapper="github-config-main")
    monkeypatch.setattr(
        config_service_module,
        "download_github_archive",
        lambda *args, **kwargs: archive,
    )

    files_response = await async_client.get(
        f"/api/v1/workspaces/{workspace_id}/configurations/{config['id']}/files",
        headers=headers,
    )
    assert files_response.status_code == 200, files_response.text
    files_payload = files_response.json()

    replace_response = await async_client.put(
        f"/api/v1/workspaces/{workspace_id}/configurations/{config['id']}/import/github",
        headers={**headers, "If-Match": files_payload["fileset_hash"]},
        json={"url": "https://github.com/octo/repo/tree/main"},
    )
    assert replace_response.status_code == 200, replace_response.text

    root = config_path(settings, workspace_id, config["id"])
    assert (root / "pyproject.toml").is_file()
    assert (root / "src" / "ade_config" / "__init__.py").is_file()


async def test_import_configuration_from_github_url_rejects_invalid_urls(
    async_client: AsyncClient,
    seed_identity,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/import/github",
        headers=headers,
        json={
            "display_name": "Invalid URL",
            "url": "https://gitlab.com/octo/repo",
        },
    )
    assert response.status_code == 400, response.text
    payload = response.json()
    assert payload["detail"]["error"] == "github_url_invalid"


async def test_import_configuration_from_github_url_maps_private_or_missing(
    async_client: AsyncClient,
    seed_identity,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)

    def _raise_not_found(*args, **kwargs):
        _ = args, kwargs
        raise ConfigImportError("github_not_found_or_private")

    monkeypatch.setattr(config_service_module, "download_github_archive", _raise_not_found)

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/import/github",
        headers=headers,
        json={
            "display_name": "Private repo",
            "url": "https://github.com/octo/private-repo",
        },
    )
    assert response.status_code == 400, response.text
    payload = response.json()
    assert payload["detail"]["error"] == "github_not_found_or_private"
    assert payload["errors"][0]["code"] == "github_not_found_or_private"


async def test_import_configuration_from_github_url_maps_rate_limits(
    async_client: AsyncClient,
    seed_identity,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)

    def _raise_rate_limit(*args, **kwargs):
        _ = args, kwargs
        raise ConfigImportError("github_rate_limited")

    monkeypatch.setattr(config_service_module, "download_github_archive", _raise_rate_limit)

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/import/github",
        headers=headers,
        json={
            "display_name": "Rate limited repo",
            "url": "https://github.com/octo/repo",
        },
    )
    assert response.status_code == 429, response.text
    payload = response.json()
    assert payload["detail"]["error"] == "github_rate_limited"


async def test_import_configuration_from_github_url_maps_download_failures(
    async_client: AsyncClient,
    seed_identity,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = seed_identity.workspace_id
    owner = seed_identity.workspace_owner
    headers = await auth_headers(async_client, email=owner.email, password=owner.password)

    def _raise_download_failed(*args, **kwargs):
        _ = args, kwargs
        raise ConfigImportError("github_download_failed")

    monkeypatch.setattr(config_service_module, "download_github_archive", _raise_download_failed)

    response = await async_client.post(
        f"/api/v1/workspaces/{workspace_id}/configurations/import/github",
        headers=headers,
        json={
            "display_name": "Download failure",
            "url": "https://github.com/octo/repo",
        },
    )
    assert response.status_code == 502, response.text
    payload = response.json()
    assert payload["detail"]["error"] == "github_download_failed"
