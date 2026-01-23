from __future__ import annotations

from datetime import timedelta

import pytest

from ade_api.settings import REPO_ROOT, Settings


def test_settings_defaults() -> None:
    """Defaults should mirror the Settings model without .env overrides."""

    settings = Settings(_env_file=None)

    assert isinstance(settings, Settings)
    assert settings.app_name == "Automatic Data Extractor API"
    assert settings.api_docs_enabled is False
    assert settings.server_public_url == "http://localhost:8000"
    assert settings.server_cors_origins == ["http://localhost:5173"]
    assert settings.database_url.endswith("data/db/ade.sqlite")
    assert settings.jwt_access_ttl == timedelta(minutes=60)
    expected_root = (REPO_ROOT / "data").resolve()
    expected_workspaces = (expected_root / "workspaces").resolve()
    expected_venvs = (expected_root / "venvs").resolve()
    assert settings.data_dir == expected_root
    assert settings.workspaces_dir == expected_workspaces
    assert settings.documents_dir == expected_workspaces
    assert settings.configs_dir == expected_workspaces
    assert settings.venvs_dir == expected_venvs
    assert settings.runs_dir == expected_workspaces
    assert settings.pip_cache_dir == (expected_root / "cache" / "pip").resolve()


def test_data_dir_propagates_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADE_DATA_DIR should become the root for workspace-owned storage."""

    monkeypatch.setenv("ADE_DATA_DIR", "./custom/data-root")

    settings = Settings(_env_file=None)

    expected_root = (REPO_ROOT / "custom" / "data-root").resolve()
    expected_workspaces = (expected_root / "workspaces").resolve()
    expected_venvs = (expected_root / "venvs").resolve()
    assert settings.data_dir == expected_root
    assert settings.workspaces_dir == expected_workspaces
    assert settings.documents_dir == expected_workspaces
    assert settings.configs_dir == expected_workspaces
    assert settings.venvs_dir == expected_venvs
    assert settings.runs_dir == expected_workspaces
