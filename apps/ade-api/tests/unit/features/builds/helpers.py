"""Helpers for build service tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from ade_api.common.ids import generate_uuid7
from ade_api.features.builds.builder import (
    BuildArtifacts,
    BuilderArtifactsEvent,
    BuilderEvent,
)
from ade_api.models import Configuration, ConfigurationStatus, Workspace


@dataclass(slots=True)
class FakeBuilder:
    events: list[BuilderEvent]

    async def build(
        self,
        *,
        build_id: str,
        workspace_id: str,
        configuration_id: str,
        venv_root: Path,
        config_path: Path,
        engine_spec: str,
        pip_cache_dir: Path | None,
        python_bin: str | None,
        timeout: float,
        fingerprint: str | None = None,
    ) -> BuildArtifacts:
        artifacts: BuildArtifacts | None = None
        async for event in self.build_stream(
            build_id=build_id,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            venv_root=venv_root,
            config_path=config_path,
            engine_spec=engine_spec,
            pip_cache_dir=pip_cache_dir,
            python_bin=python_bin,
            timeout=timeout,
            fingerprint=fingerprint,
        ):
            if isinstance(event, BuilderArtifactsEvent):
                artifacts = event.artifacts

        assert artifacts is not None
        return artifacts

    async def build_stream(
        self,
        *,
        build_id: str,
        workspace_id: str,
        configuration_id: str,
        venv_root: Path,
        config_path: Path,
        engine_spec: str,
        pip_cache_dir: Path | None,
        python_bin: str | None,
        timeout: float,
        fingerprint: str | None = None,
    ) -> AsyncIterator[BuilderEvent]:
        venv_root.mkdir(parents=True, exist_ok=True)
        for event in self.events:
            yield event


class TrackingBuilder(FakeBuilder):
    def __init__(self) -> None:
        super().__init__(events=[])
        self.invocations = 0

    async def build_stream(
        self,
        *,
        build_id: str,
        workspace_id: str,
        configuration_id: str,
        venv_root: Path,
        config_path: Path,
        engine_spec: str,
        pip_cache_dir: Path | None,
        python_bin: str | None,
        timeout: float,
        fingerprint: str | None = None,
    ) -> AsyncIterator[BuilderEvent]:
        self.invocations += 1
        async for event in super().build_stream(
            build_id=build_id,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            venv_root=venv_root,
            config_path=config_path,
            engine_spec=engine_spec,
            pip_cache_dir=pip_cache_dir,
            python_bin=python_bin,
            timeout=timeout,
            fingerprint=fingerprint,
        ):
            yield event


async def create_configuration(session):
    workspace = Workspace(name="Acme", slug=f"acme-{generate_uuid7().hex[:8]}")
    session.add(workspace)
    await session.flush()
    configuration_id = generate_uuid7()
    configuration = Configuration(
        id=configuration_id,
        workspace_id=workspace.id,
        display_name="Config",
        status=ConfigurationStatus.ACTIVE,
        content_digest="digest",
    )
    session.add(configuration)
    await session.flush()
    return workspace, configuration


async def prepare_spec(service, workspace, configuration):
    config_path = service.storage.config_path(workspace.id, configuration.id)
    (config_path / "src" / "ade_config").mkdir(parents=True, exist_ok=True)
    (config_path / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='0.0.1'\n",
        encoding="utf-8",
    )
    return await service._build_spec(
        configuration=configuration,
        workspace_id=workspace.id,
    )
