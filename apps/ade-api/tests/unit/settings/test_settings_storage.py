from __future__ import annotations

from pathlib import Path

import pytest

from ade_api.app.lifecycles import ensure_runtime_dirs
from ade_api.settings import Settings

REQUIRED_DATABASE_URL = "postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable"


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADE_DATABASE_URL", REQUIRED_DATABASE_URL)
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade-test")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")


def test_storage_directories_accept_relative_env_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADE_DATA_DIR should accept relative paths without resolution."""

    monkeypatch.chdir(tmp_path)
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ADE_DATA_DIR", "./store")
    settings = Settings(_env_file=None)

    assert settings.data_dir == Path("store")
    assert settings.workspaces_dir == Path("store/workspaces")
    assert settings.documents_dir == Path("store/workspaces")
    assert settings.configs_dir == Path("store/workspaces")
    assert settings.venvs_dir == Path("store/venvs")
    assert settings.runs_dir == Path("store/workspaces")
    assert settings.pip_cache_dir == Path("store/cache/pip")


def test_global_storage_directory_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ensure_runtime_dirs should create each configured storage directory."""

    data_dir = tmp_path / "data-root"

    _set_required_env(monkeypatch)
    monkeypatch.setenv("ADE_DATA_DIR", str(data_dir))
    settings = Settings(_env_file=None)
    ensure_runtime_dirs(settings)

    assert (data_dir / "workspaces").exists()
    assert (data_dir / "venvs").exists()
    assert (data_dir / "cache" / "pip").exists()


def test_storage_directory_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ADE_DATA_DIR should drive all derived storage paths."""

    data_dir = tmp_path / "alt-root"
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ADE_DATA_DIR", str(data_dir))
    settings = Settings(_env_file=None)

    assert settings.data_dir == data_dir
    assert settings.workspaces_dir == data_dir / "workspaces"
    assert settings.documents_dir == data_dir / "workspaces"
    assert settings.configs_dir == data_dir / "workspaces"
    assert settings.venvs_dir == data_dir / "venvs"
    assert settings.runs_dir == data_dir / "workspaces"
    assert settings.pip_cache_dir == data_dir / "cache" / "pip"


def test_blob_backend_requires_container_and_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADE_DATABASE_URL", REQUIRED_DATABASE_URL)
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    with pytest.raises(ValueError, match="ADE_BLOB_CONTAINER"):
        Settings(_env_file=None)

    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade")
    with pytest.raises(ValueError, match="ADE_BLOB_CONNECTION_STRING or ADE_BLOB_ACCOUNT_URL"):
        Settings(_env_file=None)

    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_BLOB_ACCOUNT_URL", "https://example.blob.core.windows.net")
    with pytest.raises(ValueError, match="ADE_BLOB_ACCOUNT_URL must be unset"):
        Settings(_env_file=None)


def test_blob_backend_accepts_managed_identity_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADE_DATABASE_URL", REQUIRED_DATABASE_URL)
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_BLOB_ACCOUNT_URL", "https://example.blob.core.windows.net/")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade")
    monkeypatch.setenv("ADE_BLOB_PREFIX", "/workspaces/")

    settings = Settings(_env_file=None)

    assert settings.blob_account_url == "https://example.blob.core.windows.net"
    assert settings.blob_container == "ade"
    assert settings.blob_prefix == "workspaces"


def test_blob_backend_accepts_connection_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADE_DATABASE_URL", REQUIRED_DATABASE_URL)
    monkeypatch.setenv("ADE_SECRET_KEY", "test-secret-key-for-tests-please-change")
    monkeypatch.setenv("ADE_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setenv("ADE_BLOB_CONTAINER", "ade")

    settings = Settings(_env_file=None)

    assert settings.blob_connection_string == "UseDevelopmentStorage=true"
    assert settings.blob_container == "ade"
