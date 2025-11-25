"""Unit tests for the virtual environment builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from ade_api.features.builds.builder import (
    BuilderLogEvent,
    VirtualEnvironmentBuilder,
)

pytestmark = pytest.mark.asyncio


async def test_builder_installs_dependencies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Pip installs should include dependencies for engine and config packages."""

    builder = VirtualEnvironmentBuilder()
    commands: list[list[str]] = []

    async def _prepare_target(target: Path) -> None:  # noqa: D401 - stubbed in test
        return None

    async def _stream_command(  # noqa: D401 - stubbed in test
        command: list[str],
        *,
        timeout: float,
        env: dict[str, str] | None = None,
        build_id: str,
    ):
        commands.append(command)
        yield BuilderLogEvent(message=f"ran {' '.join(command)}")

    async def _capture(  # noqa: D401 - stubbed in test
        command: list[str],
        *,
        timeout: float,
        env: dict[str, str] | None = None,
        build_id: str,
    ) -> str:
        if "sys.version_info" in command[-1]:
            return "3.12.1"
        return "0.2.0"

    async def _write_metadata(target: Path, payload: dict[str, str]) -> None:  # noqa: D401
        return None

    monkeypatch.setattr(builder, "_prepare_target", _prepare_target)
    monkeypatch.setattr(builder, "_stream_command", _stream_command)
    monkeypatch.setattr(builder, "_capture", _capture)
    monkeypatch.setattr(builder, "_write_metadata", _write_metadata)

    engine_spec = "apps/ade-engine"
    config_root = tmp_path / "config"
    config_root.mkdir(parents=True)

    _ = [
        event
        async for event in builder.build_stream(
            build_id="build",
            workspace_id="workspace",
            config_id="config",
            target_path=tmp_path / "venv",
            config_path=config_root,
            engine_spec=engine_spec,
            pip_cache_dir=None,
            python_bin=None,
            timeout=1.0,
        )
    ]

    engine_install = next(cmd for cmd in commands if engine_spec in cmd)
    config_install = next(cmd for cmd in commands if str(config_root) in cmd)

    assert "--no-deps" not in engine_install
    assert "--no-deps" not in config_install
