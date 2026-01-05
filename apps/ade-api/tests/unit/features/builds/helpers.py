"""Helpers for build service tests."""

from __future__ import annotations

from pathlib import Path

from ade_api.common.ids import generate_uuid7
from ade_api.features.configs.storage import ConfigStorage
from ade_api.models import Configuration, ConfigurationStatus, Workspace


async def create_configuration(session) -> tuple[Workspace, Configuration]:
    workspace = Workspace(name="Acme", slug=f"acme-{generate_uuid7().hex[:8]}")
    session.add(workspace)
    await session.flush()
    configuration = Configuration(
        id=generate_uuid7(),
        workspace_id=workspace.id,
        display_name="Config",
        status=ConfigurationStatus.ACTIVE,
        content_digest="digest",
    )
    session.add(configuration)
    await session.flush()
    return workspace, configuration


def ensure_config_package(
    storage: ConfigStorage,
    *,
    workspace_id,
    configuration_id,
) -> Path:
    config_path = storage.config_path(workspace_id, configuration_id)
    (config_path / "src" / "ade_config").mkdir(parents=True, exist_ok=True)
    (config_path / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='0.0.1'\n",
        encoding="utf-8",
    )
    return config_path
