"""Workspace-scoped filesystem layout helpers.

These helpers live in ``infra.storage`` to keep storage concerns grouped and
avoid root-level one-off modules.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from ade_api.settings import Settings

__all__ = [
    "build_venv_marker_path",
    "build_venv_path",
    "build_venv_root",
    "build_venv_temp_path",
    "workspace_config_root",
    "workspace_documents_root",
    "workspace_root",
    "workspace_run_root",
    "workspace_venvs_root",
]


def _workspace_base(root: Path, workspace_id: UUID | object) -> Path:
    return Path(root) / str(workspace_id)


def workspace_root(settings: Settings, workspace_id: UUID) -> Path:
    """Base directory for a workspace under the configured workspaces root."""

    return _workspace_base(settings.workspaces_dir, workspace_id)


def workspace_config_root(
    settings: Settings,
    workspace_id: UUID,
    configuration_id: UUID | None = None,
) -> Path:
    """Path to a workspace's config packages root or a specific config."""

    root = _workspace_base(settings.configs_dir, workspace_id) / "config_packages"
    return root if configuration_id is None else root / str(configuration_id)


def workspace_run_root(
    settings: Settings,
    workspace_id: UUID,
    run_id: UUID | None = None,
) -> Path:
    """Path to a workspace's runs root or a specific run directory."""

    root = _workspace_base(settings.runs_dir, workspace_id) / "runs"
    return root if run_id is None else root / str(run_id)


def workspace_documents_root(settings: Settings, workspace_id: UUID) -> Path:
    """Path to a workspace's documents directory."""

    return _workspace_base(settings.documents_dir, workspace_id) / "documents"


def workspace_venvs_root(settings: Settings, workspace_id: UUID) -> Path:
    """Root of all venvs for a workspace under ADE_VENVS_DIR."""

    return _workspace_base(settings.venvs_dir, workspace_id)


def build_venv_root(
    settings: Settings,
    workspace_id: UUID,
    configuration_id: UUID,
    build_id: UUID,
) -> Path:
    """Root folder reserved for a specific build."""

    return workspace_venvs_root(settings, workspace_id) / str(configuration_id) / str(build_id)


def build_venv_path(
    settings: Settings,
    workspace_id: UUID,
    configuration_id: UUID,
    build_id: UUID,
) -> Path:
    """Path to the finalized virtual environment directory for a build."""

    return build_venv_root(settings, workspace_id, configuration_id, build_id) / ".venv"


def build_venv_temp_path(
    settings: Settings,
    workspace_id: UUID,
    configuration_id: UUID,
    build_id: UUID,
) -> Path:
    """Temporary venv path used during build before atomic rename."""

    return build_venv_root(settings, workspace_id, configuration_id, build_id) / ".venv.tmp"


def build_venv_marker_path(
    settings: Settings,
    workspace_id: UUID,
    configuration_id: UUID,
    build_id: UUID,
) -> Path:
    """Marker file capturing build metadata inside the venv."""

    return build_venv_path(settings, workspace_id, configuration_id, build_id) / "ade_build.json"
