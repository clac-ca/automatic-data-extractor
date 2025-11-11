"""Utilities to create isolated Python virtual environments for builds."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from fastapi.concurrency import run_in_threadpool

from .exceptions import BuildExecutionError

__all__ = [
    "BuildArtifacts",
    "VirtualEnvironmentBuilder",
]


@dataclass(slots=True)
class BuildArtifacts:
    """Metadata captured from a successful build."""

    python_version: str
    engine_version: str


class VirtualEnvironmentBuilder:
    """Create virtual environments containing ADE engine + config package."""

    def __init__(self) -> None:
        self._platform_bin = "Scripts" if os.name == "nt" else "bin"

    async def build(
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
    ) -> BuildArtifacts:
        """Create a virtual environment at ``target_path`` and install packages."""

        interpreter = python_bin or sys.executable
        await self._prepare_target(target_path)

        try:
            await self._run(
                [interpreter, "-m", "venv", str(target_path)],
                timeout=timeout,
            )
            venv_python = self._venv_python(target_path)
            await self._run(
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
                env=self._build_env(pip_cache_dir),
            )
            await self._run(
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
                env=self._build_env(pip_cache_dir),
            )
            await self._run(
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
                env=self._build_env(pip_cache_dir),
            )

            await self._run(
                [str(venv_python), "-I", "-B", "-c", "import ade_engine, ade_config"],
                timeout=timeout,
                env=self._build_env(pip_cache_dir),
            )

            python_version = (
                await self._capture(
                    [
                        str(venv_python),
                        "-c",
                        "import sys; print('.'.join(map(str, sys.version_info[:3])))",
                    ],
                    timeout=timeout,
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
                )
            ).strip()

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

            return BuildArtifacts(
                python_version=python_version,
                engine_version=engine_version,
            )
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

    async def _run(
        self,
        command: list[str],
        *,
        timeout: float,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        def _call() -> subprocess.CompletedProcess[str]:
            env_vars = os.environ.copy()
            if env:
                env_vars.update(env)
            return subprocess.run(
                command,
                check=True,
                text=True,
                capture_output=True,
                env=env_vars,
                timeout=timeout,
            )

        return await run_in_threadpool(_call)

    async def _capture(
        self,
        command: list[str],
        *,
        timeout: float,
    ) -> str:
        completed = await self._run(command, timeout=timeout)
        return (completed.stdout or "").strip()

    async def _write_metadata(self, target: Path, payload: Mapping[str, object]) -> None:
        runtime_dir = target / "ade-runtime"
        packages_txt = runtime_dir / "packages.txt"
        build_json = runtime_dir / "build.json"

        def _write() -> None:
            runtime_dir.mkdir(parents=True, exist_ok=True)
            packages_txt.write_text("", encoding="utf-8")
            build_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        await run_in_threadpool(_write)

    def _build_env(self, pip_cache_dir: Path | None) -> Mapping[str, str] | None:
        if pip_cache_dir is None:
            return None
        return {"PIP_CACHE_DIR": str(pip_cache_dir)}
