from pathlib import Path

import pytest

from ade_storage import (
    workspace_config_root,
    workspace_documents_root,
    workspace_root,
    workspace_run_root,
    workspace_venvs_root,
)
from ade_api.settings import Settings


def test_workspace_layout_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
        secret_key="test-secret-key-for-tests-please-change",
    )

    workspace_id = "acme-ws"
    config_id = "cfg-01"
    run_id = "run-456"

    base = (tmp_path / "data" / "workspaces" / workspace_id).resolve()
    assert workspace_root(settings, workspace_id) == base
    assert workspace_documents_root(settings, workspace_id) == base / "files"
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
    assert (
        workspace_venvs_root(settings, workspace_id)
        == (tmp_path / "data" / "venvs" / workspace_id).resolve()
    )


def test_workspace_layout_uses_data_dir(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data-root",
        database_url="postgresql+psycopg://ade:ade@localhost:5432/ade?sslmode=disable",
        blob_container="ade-test",
        blob_connection_string="UseDevelopmentStorage=true",
        secret_key="test-secret-key-for-tests-please-change",
    )

    workspace_id = "override-ws"
    config_id = "cfg-99"

    assert (
        workspace_documents_root(settings, workspace_id)
        == (tmp_path / "data-root" / "workspaces" / workspace_id / "files").resolve()
    )
    assert (
        workspace_config_root(settings, workspace_id, config_id)
        == (tmp_path / "data-root" / "workspaces" / workspace_id / "config_packages" / config_id).resolve()
    )
    assert (
        workspace_run_root(settings, workspace_id)
        == (tmp_path / "data-root" / "workspaces" / workspace_id / "runs").resolve()
    )
    assert (
        workspace_run_root(settings, workspace_id, "run-123")
        == (tmp_path / "data-root" / "workspaces" / workspace_id / "runs" / "run-123").resolve()
    )
    assert (
        workspace_venvs_root(settings, workspace_id)
        == (tmp_path / "data-root" / "venvs" / workspace_id).resolve()
    )
