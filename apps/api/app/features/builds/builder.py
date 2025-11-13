"""Async virtual environment builder that emits streaming events."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import AsyncIterator, Mapping

from fastapi.concurrency import run_in_threadpool

from .exceptions import BuildExecutionError

__all__ = [
    "BuildArtifacts",
    "BuildStep",
    "BuilderArtifactsEvent",
    "BuilderEvent",
    "BuilderLogEvent",
    "BuilderStepEvent",
    "VirtualEnvironmentBuilder",
]


@dataclass(slots=True)
class BuildArtifacts:
    """Metadata captured from a successful build."""

    python_version: str
    engine_version: str


class BuildStep(str, Enum):
    """Ordered phases executed by the builder."""

    CREATE_VENV = "create_venv"
    UPGRADE_PIP = "upgrade_pip"
    INSTALL_ENGINE = "install_engine"
    INSTALL_CONFIG = "install_config"
    VERIFY_IMPORTS = "verify_imports"
    COLLECT_METADATA = "collect_metadata"


@dataclass(slots=True)
class BuilderStepEvent:
    step: BuildStep
    message: str | None = None


@dataclass(slots=True)
class BuilderLogEvent:
    message: str
    stream: str = "stdout"


@dataclass(slots=True)
class BuilderArtifactsEvent:
    artifacts: BuildArtifacts


BuilderEvent = BuilderStepEvent | BuilderLogEvent | BuilderArtifactsEvent


class VirtualEnvironmentBuilder:
    """Create virtual environments containing ADE engine + config package."""

    def __init__(self) -> None:
        self._platform_bin = "Scripts" if os.name == "nt" else "bin"

    async def build_stream(
        self,
        *,
        build_id: str,
        workspace_id: str,
        config_id: str,
        target_path: Path,
        config_path: Path,
        engine_spec: str,
        pip_cache_dir: Path | None,
        python_bin: str | None,
        timeout: float,
    ) -> AsyncIterator[BuilderEvent]:
        """Yield builder events while provisioning the virtual environment."""

        interpreter = python_bin or sys.executable
        await self._prepare_target(target_path)
        env = self._build_env(pip_cache_dir)

        try:
            yield BuilderStepEvent(BuildStep.CREATE_VENV, "Creating virtual environment")
            async for event in self._stream_command(
                [interpreter, "-m", "venv", str(target_path)],
                timeout=timeout,
                env=None,
                build_id=build_id,
            ):
                yield event

            venv_python = self._venv_python(target_path)
            yield BuilderStepEvent(BuildStep.UPGRADE_PIP, "Upgrading pip/setuptools/wheel")
            async for event in self._stream_command(
                [
                    str(venv_python),
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "pip",
                    "wheel",
                    "setuptools",
                ],
                timeout=timeout,
                env=env,
                build_id=build_id,
            ):
                yield event

            yield BuilderStepEvent(BuildStep.INSTALL_ENGINE, f"Installing engine: {engine_spec}")
            async for event in self._stream_command(
                [
                    str(venv_python),
                    "-m",
                    "pip",
                    "install",
                    "--no-input",
                    "--no-deps",
                    engine_spec,
                ],
                timeout=timeout,
                env=env,
                build_id=build_id,
            ):
                yield event

            yield BuilderStepEvent(BuildStep.INSTALL_CONFIG, "Installing configuration package")
            async for event in self._stream_command(
                [
                    str(venv_python),
                    "-m",
                    "pip",
                    "install",
                    "--no-input",
                    "--no-deps",
                    str(config_path),
                ],
                timeout=timeout,
                env=env,
                build_id=build_id,
            ):
                yield event

            yield BuilderStepEvent(BuildStep.VERIFY_IMPORTS, "Verifying ade_engine and ade_config imports")
            async for event in self._stream_command(
                [str(venv_python), "-I", "-B", "-c", "import ade_engine, ade_config"],
                timeout=timeout,
                env=env,
                build_id=build_id,
            ):
                yield event

            yield BuilderStepEvent(BuildStep.COLLECT_METADATA, "Collecting interpreter metadata")
            python_version = (
                await self._capture(
                    [
                        str(venv_python),
                        "-c",
                        "import sys; print('.'.join(map(str, sys.version_info[:3])))",
                    ],
                    timeout=timeout,
                    build_id=build_id,
                )
            ).strip()
            engine_version = (
                await self._capture(
                    [
                        str(venv_python),
                        "-c",
                        "import importlib.metadata as m; print(m.version('ade-engine'))",
                    ],
                    timeout=timeout,
                    build_id=build_id,
                )
            ).strip()

            artifacts = BuildArtifacts(
                python_version=python_version,
                engine_version=engine_version,
            )
            await self._write_metadata(
                target_path,
                {
                    "build_id": build_id,
                    "workspace_id": workspace_id,
                    "config_id": config_id,
                    "python_version": python_version,
                    "engine_version": engine_version,
                },
            )

            yield BuilderArtifactsEvent(artifacts)
        except Exception as exc:  # pragma: no cover - defensive cleanup
            await self._remove_target(target_path)
            message = (
                f"Failed to build venv for workspace={workspace_id} config={config_id}: {exc}"
            )
            raise BuildExecutionError(message, build_id=build_id) from exc

    async def _prepare_target(self, target: Path) -> None:
        def _prepare() -> None:
            if target.exists():
                shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True)

        await run_in_threadpool(_prepare)

    async def _remove_target(self, target: Path) -> None:
        def _remove() -> None:
            shutil.rmtree(target, ignore_errors=True)

        await run_in_threadpool(_remove)

    def _venv_python(self, target: Path) -> Path:
        executable = "python.exe" if os.name == "nt" else "python"
        return target / self._platform_bin / executable

    async def _stream_command(
        self,
        command: list[str],
        *,
        timeout: float,
        env: Mapping[str, str] | None = None,
        build_id: str,
    ) -> AsyncIterator[BuilderLogEvent]:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=self._merge_env(env),
        )
        assert process.stdout is not None

        async def _reader() -> AsyncIterator[BuilderLogEvent]:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip("\n")
                yield BuilderLogEvent(message=text)

        reader = _reader()
        try:
            async with asyncio.timeout(timeout):
                async for event in reader:
                    yield event
        except asyncio.TimeoutError as exc:  # pragma: no cover - should be prevented by caller
            process.kill()
            await process.wait()
            raise BuildExecutionError(
                f"Command timed out after {timeout}s: {' '.join(command)}",
                build_id=build_id,
            ) from exc

        return_code = await process.wait()
        if return_code != 0:
            raise BuildExecutionError(
                f"Command failed with exit code {return_code}: {' '.join(command)}",
                build_id=build_id,
            )

    async def _capture(
        self,
        command: list[str],
        *,
        timeout: float,
        env: Mapping[str, str] | None = None,
        build_id: str,
    ) -> str:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=self._merge_env(env),
        )
        assert process.stdout is not None
        try:
            async with asyncio.timeout(timeout):
                output = await process.stdout.read()
        except asyncio.TimeoutError as exc:  # pragma: no cover - defensive
            process.kill()
            await process.wait()
            raise BuildExecutionError(
                f"Command timed out after {timeout}s: {' '.join(command)}",
                build_id=build_id,
            ) from exc
        return_code = await process.wait()
        if return_code != 0:
            raise BuildExecutionError(
                f"Command failed with exit code {return_code}: {' '.join(command)}",
                build_id=build_id,
            )
        return output.decode("utf-8", errors="replace")

    async def _write_metadata(self, target: Path, payload: dict[str, str]) -> None:
        runtime_dir = target / "ade-runtime"
        metadata_path = runtime_dir / "build.json"
        packages_path = runtime_dir / "packages.txt"

        def _write() -> None:
            runtime_dir.mkdir(parents=True, exist_ok=True)
            metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            packages_path.write_text("ade-engine\nade-config", encoding="utf-8")

        await run_in_threadpool(_write)

    def _build_env(self, pip_cache_dir: Path | None) -> dict[str, str]:
        if pip_cache_dir is None:
            return {}
        return {
            "PIP_NO_INPUT": "1",
            "PIP_CACHE_DIR": str(pip_cache_dir),
        }

    def _merge_env(self, env: Mapping[str, str] | None) -> Mapping[str, str] | None:
        if env is None:
            return None
        merged = os.environ.copy()
        merged.update(env)
        return merged

