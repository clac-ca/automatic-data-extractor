from pathlib import Path

import pytest

from ade_api.infra.storage import (
    build_venv_path,
    build_venv_root,
    build_venv_temp_path,
    workspace_config_root,
    workspace_documents_root,
    workspace_root,
    workspace_run_root,
)
from ade_api.settings import DEFAULT_VENVS_DIR, Settings


def test_workspace_layout_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADE_VENVS_DIR", raising=False)
    settings = Settings(workspaces_dir=tmp_path / "workspaces")

    workspace_id = "acme-ws"
    config_id = "cfg-01"
    run_id = "run-456"

    base = (tmp_path / "workspaces" / workspace_id).resolve()
    assert workspace_root(settings, workspace_id) == base
    assert workspace_documents_root(settings, workspace_id) == base / "documents"
    assert (
        workspace_config_root(
            settings,
            workspace_id,
            config_id,
        )
        == base / "config_packages" / config_id
    )
    assert workspace_run_root(settings, workspace_id) == base / "runs"
    assert workspace_run_root(settings, workspace_id, run_id) == base / "runs" / run_id
    expected_root = (DEFAULT_VENVS_DIR / workspace_id / config_id / "build-1").resolve()
    assert build_venv_root(settings, workspace_id, config_id, "build-1") == expected_root
    assert build_venv_path(settings, workspace_id, config_id, "build-1") == expected_root / ".venv"
    assert (
        build_venv_temp_path(settings, workspace_id, config_id, "build-1")
        == expected_root / ".venv.tmp"
    )


def test_workspace_layout_respects_overrides(tmp_path: Path) -> None:
    settings = Settings(
        workspaces_dir=tmp_path / "workspaces",
        documents_dir=tmp_path / "docs-override",
        configs_dir=tmp_path / "configs-override",
        runs_dir=tmp_path / "runs-override",
        venvs_dir=tmp_path / "venvs-override",
    )

    workspace_id = "override-ws"
    config_id = "cfg-99"

    assert (
        workspace_documents_root(settings, workspace_id)
        == (tmp_path / "docs-override" / workspace_id / "documents").resolve()
    )
    assert (
        workspace_config_root(settings, workspace_id, config_id)
        == (tmp_path / "configs-override" / workspace_id / "config_packages" / config_id).resolve()
    )
    assert (
        workspace_run_root(settings, workspace_id)
        == (tmp_path / "runs-override" / workspace_id / "runs").resolve()
    )
    assert (
        workspace_run_root(settings, workspace_id, "run-123")
        == (tmp_path / "runs-override" / workspace_id / "runs" / "run-123").resolve()
    )
    expected_root = (tmp_path / "venvs-override" / workspace_id / config_id / "build-abc").resolve()
    assert build_venv_root(settings, workspace_id, config_id, "build-abc") == expected_root
    assert (
        build_venv_path(settings, workspace_id, config_id, "build-abc") == expected_root / ".venv"
    )
    assert (
        build_venv_temp_path(settings, workspace_id, config_id, "build-abc")
        == expected_root / ".venv.tmp"
    )
