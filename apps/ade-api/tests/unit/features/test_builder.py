"""Unit tests for the virtual environment builder."""

from __future__ import annotations

import json
from pathlib import Path
import uuid

import pytest

from ade_api.features.builds.builder import (
    BuilderLogEvent,
    VirtualEnvironmentBuilder,
)

pytestmark = pytest.mark.asyncio


async def test_builder_installs_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pip installs should include dependencies for engine and config packages."""

    builder = VirtualEnvironmentBuilder()
    commands: list[list[str]] = []

    async def _prepare_target(root: Path, temp_target: Path) -> None:  # noqa: D401
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
            return "3.14.0"
        return "1.6.1"

    async def _write_metadata(target: Path, payload: dict[str, str | None]) -> None:  # noqa: D401
        return None

    async def _finalize_target(temp_target: Path, final_target: Path) -> None:  # noqa: D401
        return None

    monkeypatch.setattr(builder, "_prepare_target", _prepare_target)
    monkeypatch.setattr(builder, "_stream_command", _stream_command)
    monkeypatch.setattr(builder, "_capture", _capture)
    monkeypatch.setattr(builder, "_write_metadata", _write_metadata)
    monkeypatch.setattr(builder, "_finalize_target", _finalize_target)

    engine_spec = "apps/ade-engine"
    config_root = tmp_path / "config"
    config_root.mkdir(parents=True)

    _ = [
        event
        async for event in builder.build_stream(
            build_id="build",
            workspace_id="workspace",
            configuration_id="config",
            venv_root=tmp_path / "venv",
            config_path=config_root,
            engine_spec=engine_spec,
            pip_cache_dir=None,
            python_bin=None,
            timeout=1.0,
            fingerprint=None,
        )
    ]

    engine_install = next(cmd for cmd in commands if engine_spec in cmd)
    config_install = next(cmd for cmd in commands if str(config_root) in cmd)

    assert "--no-deps" not in engine_install
    assert "--no-deps" not in config_install


async def test_write_metadata_serializes_uuid(tmp_path: Path) -> None:
    """Metadata payload should be JSON-serializable even if UUIDs are passed through."""

    builder = VirtualEnvironmentBuilder()
    payload = {
        "build_id": uuid.uuid4(),
        "workspace_id": uuid.uuid4(),
        "configuration_id": uuid.uuid4(),
        "python_version": "3.11.8",
        "engine_version": "1.6.1",
        "fingerprint": "abc123",
    }

    await builder._write_metadata(tmp_path, payload)  # type: ignore[arg-type]

    build_json = json.loads((tmp_path / "ade-runtime" / "build.json").read_text())
    marker_json = json.loads((tmp_path / "ade_build.json").read_text())

    for key, value in payload.items():
        expected = str(value) if value is not None else None
        assert build_json[key] == expected
        assert marker_json[key] == expected
