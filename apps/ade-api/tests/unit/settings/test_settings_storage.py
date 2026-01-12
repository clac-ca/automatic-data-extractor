from __future__ import annotations

from pathlib import Path

import pytest

from ade_api.app.lifecycles import ensure_runtime_dirs
from ade_api.settings import REPO_ROOT, Settings


def test_storage_directories_resolve_relative_env_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Storage directory env vars should resolve relative paths to repo-root absolute ones."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ADE_WORKSPACES_DIR", "./store/workspaces")
    monkeypatch.setenv("ADE_DOCUMENTS_DIR", "./store/documents")
    monkeypatch.setenv("ADE_CONFIGS_DIR", "./store/configs")
    monkeypatch.setenv("ADE_VENVS_DIR", "./store/venvs")
    monkeypatch.setenv("ADE_RUNS_DIR", "./store/runs")
    monkeypatch.setenv("ADE_PIP_CACHE_DIR", "./cache/pip")
    settings = Settings(_env_file=None)

    assert settings.workspaces_dir == (REPO_ROOT / "store" / "workspaces").resolve()
    assert settings.documents_dir == (REPO_ROOT / "store" / "documents").resolve()
    assert settings.configs_dir == (REPO_ROOT / "store" / "configs").resolve()
    assert settings.venvs_dir == (REPO_ROOT / "store" / "venvs").resolve()
    assert settings.runs_dir == (REPO_ROOT / "store" / "runs").resolve()
    assert settings.pip_cache_dir == (REPO_ROOT / "cache" / "pip").resolve()


def test_global_storage_directory_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ensure_runtime_dirs should create each configured storage directory."""

    workspaces_dir = tmp_path / "workspaces-root"
    documents_dir = tmp_path / "docs-root"
    configs_dir = tmp_path / "config-root"
    venvs_dir = tmp_path / "venv-root"
    runs_dir = tmp_path / "runs-root"
    pip_cache_dir = tmp_path / "cache-root"

    monkeypatch.setenv("ADE_WORKSPACES_DIR", str(workspaces_dir))
    monkeypatch.setenv("ADE_DOCUMENTS_DIR", str(documents_dir))
    monkeypatch.setenv("ADE_CONFIGS_DIR", str(configs_dir))
    monkeypatch.setenv("ADE_VENVS_DIR", str(venvs_dir))
    monkeypatch.setenv("ADE_RUNS_DIR", str(runs_dir))
    monkeypatch.setenv("ADE_PIP_CACHE_DIR", str(pip_cache_dir))
    settings = Settings(_env_file=None)
    ensure_runtime_dirs(settings)

    assert workspaces_dir.exists()
    assert documents_dir.exists()
    assert configs_dir.exists()
    assert venvs_dir.exists()
    assert runs_dir.exists()
    assert pip_cache_dir.exists()


def test_storage_directory_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit ADE_*_DIR overrides should be honoured."""

    documents_dir = tmp_path / "alt-documents"
    configs_dir = tmp_path / "alt-configs"
    venvs_dir = tmp_path / "alt-venvs"
    runs_dir = tmp_path / "alt-runs"
    pip_cache_dir = tmp_path / "alt-cache" / "pip"
    workspaces_dir = tmp_path / "alt-workspaces"

    monkeypatch.setenv("ADE_WORKSPACES_DIR", str(workspaces_dir))
    monkeypatch.setenv("ADE_DOCUMENTS_DIR", str(documents_dir))
    monkeypatch.setenv("ADE_CONFIGS_DIR", str(configs_dir))
    monkeypatch.setenv("ADE_VENVS_DIR", str(venvs_dir))
    monkeypatch.setenv("ADE_RUNS_DIR", str(runs_dir))
    monkeypatch.setenv("ADE_PIP_CACHE_DIR", str(pip_cache_dir))
    settings = Settings(_env_file=None)

    assert settings.workspaces_dir == workspaces_dir.resolve()
    assert settings.documents_dir == documents_dir.resolve()
    assert settings.configs_dir == configs_dir.resolve()
    assert settings.venvs_dir == venvs_dir.resolve()
    assert settings.runs_dir == runs_dir.resolve()
    assert settings.pip_cache_dir == pip_cache_dir.resolve()
