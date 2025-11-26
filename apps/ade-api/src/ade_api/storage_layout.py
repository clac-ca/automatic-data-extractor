"""Helpers for workspace-scoped storage paths."""

from __future__ import annotations

from pathlib import Path

from ade_api.settings import Settings

__all__ = [
    "config_venv_path",
    "workspace_config_root",
    "workspace_documents_root",
    "workspace_root",
    "workspace_run_root",
]


def _workspace_base(root: Path, workspace_id: str) -> Path:
    return Path(root) / workspace_id


def workspace_root(settings: Settings, workspace_id: str) -> Path:
    """Base directory for a workspace under the configured workspaces root."""

    return _workspace_base(settings.workspaces_dir, workspace_id)


def workspace_config_root(
    settings: Settings,
    workspace_id: str,
    configuration_id: str | None = None,
) -> Path:
    """Path to a workspace's config packages root or a specific config."""

    root = _workspace_base(settings.configs_dir, workspace_id) / "config_packages"
    return root if configuration_id is None else root / configuration_id


def workspace_run_root(
    settings: Settings,
    workspace_id: str,
    run_id: str | None = None,
) -> Path:
    """Path to a workspace's runs root or a specific run directory."""

    root = _workspace_base(settings.runs_dir, workspace_id) / "runs"
    return root if run_id is None else root / run_id


def workspace_documents_root(settings: Settings, workspace_id: str) -> Path:
    """Path to a workspace's documents directory."""

    return _workspace_base(settings.documents_dir, workspace_id) / "documents"


def config_venv_path(
    settings: Settings,
    workspace_id: str,
    configuration_id: str,
) -> Path:
    """Path to the single active venv for a configuration."""

    return workspace_config_root(settings, workspace_id, configuration_id) / ".venv"
