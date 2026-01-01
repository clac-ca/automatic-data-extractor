from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path

import pytest

from ade_api.settings import Settings, get_settings, reload_settings


def test_settings_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Defaults should mirror the Settings model without .env overrides."""

    monkeypatch.chdir(tmp_path)
    reload_settings()
    settings = get_settings()

    assert isinstance(settings, Settings)
    assert settings.app_name == "Automatic Data Extractor API"
    assert settings.api_docs_enabled is False
    assert settings.server_public_url == "http://localhost:8000"
    assert settings.server_cors_origins == ["http://localhost:5173"]
    assert settings.database_url.endswith("data/db/ade.sqlite")
    assert settings.jwt_access_ttl == timedelta(minutes=60)
    expected_root = (tmp_path / "data").resolve()
    expected_workspaces = (expected_root / "workspaces").resolve()
    expected_venvs = (Path(tempfile.gettempdir()) / "ade-venvs").resolve()
    assert settings.workspaces_dir == expected_workspaces
    assert settings.documents_dir == expected_workspaces
    assert settings.configs_dir == expected_workspaces
    assert settings.venvs_dir == expected_venvs
    assert settings.runs_dir == expected_workspaces
    assert settings.pip_cache_dir == (expected_root / "cache" / "pip").resolve()


def test_workspaces_dir_propagates_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """workspaces_dir should become the default root for workspace-owned storage."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ADE_WORKSPACES_DIR", "./custom/workspaces")
    reload_settings()

    settings = get_settings()

    expected_root = (tmp_path / "custom" / "workspaces").resolve()
    expected_venvs = (Path(tempfile.gettempdir()) / "ade-venvs").resolve()
    assert settings.workspaces_dir == expected_root
    assert settings.documents_dir == expected_root
    assert settings.configs_dir == expected_root
    assert settings.venvs_dir == expected_venvs
    assert settings.runs_dir == expected_root
