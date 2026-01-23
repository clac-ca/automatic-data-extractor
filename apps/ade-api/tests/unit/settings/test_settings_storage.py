from __future__ import annotations

from pathlib import Path

import pytest

from ade_api.app.lifecycles import ensure_runtime_dirs
from ade_api.settings import REPO_ROOT, Settings


def test_storage_directories_resolve_relative_env_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADE_DATA_DIR should resolve relative paths to repo-root absolute ones."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ADE_DATA_DIR", "./store")
    settings = Settings(_env_file=None)

    assert settings.data_dir == (REPO_ROOT / "store").resolve()
    assert settings.workspaces_dir == (REPO_ROOT / "store" / "workspaces").resolve()
    assert settings.documents_dir == (REPO_ROOT / "store" / "workspaces").resolve()
    assert settings.configs_dir == (REPO_ROOT / "store" / "workspaces").resolve()
    assert settings.venvs_dir == (REPO_ROOT / "store" / "venvs").resolve()
    assert settings.runs_dir == (REPO_ROOT / "store" / "workspaces").resolve()
    assert settings.pip_cache_dir == (REPO_ROOT / "store" / "cache" / "pip").resolve()


def test_global_storage_directory_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ensure_runtime_dirs should create each configured storage directory."""

    data_dir = tmp_path / "data-root"

    monkeypatch.setenv("ADE_DATA_DIR", str(data_dir))
    settings = Settings(_env_file=None)
    ensure_runtime_dirs(settings)

    assert (data_dir / "workspaces").exists()
    assert (data_dir / "venvs").exists()
    assert (data_dir / "cache" / "pip").exists()


def test_storage_directory_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ADE_DATA_DIR should drive all derived storage paths."""

    data_dir = tmp_path / "alt-root"
    monkeypatch.setenv("ADE_DATA_DIR", str(data_dir))
    settings = Settings(_env_file=None)

    assert settings.data_dir == data_dir.resolve()
    assert settings.workspaces_dir == (data_dir / "workspaces").resolve()
    assert settings.documents_dir == (data_dir / "workspaces").resolve()
    assert settings.configs_dir == (data_dir / "workspaces").resolve()
    assert settings.venvs_dir == (data_dir / "venvs").resolve()
    assert settings.runs_dir == (data_dir / "workspaces").resolve()
    assert settings.pip_cache_dir == (data_dir / "cache" / "pip").resolve()
