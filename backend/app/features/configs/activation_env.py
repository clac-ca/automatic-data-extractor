"""Helpers for building and reading activation environments."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import venv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from backend.app.features.configs.models import Config, ConfigVersion
from backend.app.features.configs.spec import ManifestV1
from backend.app.shared.core.config import Settings
from backend.app.shared.core.time import utc_now

from .storage import ConfigStorage

__all__ = [
    "ActivationEnvironmentManager",
    "ActivationError",
    "ActivationMetadata",
    "ActivationMetadataStore",
]


@dataclass(slots=True)
class ActivationMetadata:
    """Snapshot of activation environment state for a config version."""

    status: str
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    venv_path: Path | None
    python_executable: Path | None
    packages_path: Path | None
    install_log_path: Path | None
    hooks_path: Path | None
    annotations: list[dict[str, Any]]
    diagnostics: list[dict[str, Any]]

    @property
    def ready(self) -> bool:
        return (
            self.status == "succeeded"
            and self.python_executable is not None
            and self.python_executable.exists()
        )


class ActivationError(Exception):
    """Raised when activation fails to build a runnable environment."""

    def __init__(self, message: str, *, diagnostics: Sequence[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.diagnostics = list(diagnostics or [])


class ActivationMetadataStore:
    """Load activation metadata persisted alongside config packages."""

    _RESULT_FILENAME = "result.json"
    _HOOKS_FILENAME = "hooks.json"
    _VENV_INFO_FILENAME = "venv_path.json"

    def __init__(self, storage: ConfigStorage) -> None:
        self._storage = storage

    def load(self, *, config_id: str, version: ConfigVersion) -> ActivationMetadata | None:
        activation_dir = self._storage.activation_dir(config_id, version.sequence)
        result_path = activation_dir / self._RESULT_FILENAME
        if not result_path.exists():
            return None

        payload = json.loads(result_path.read_text(encoding="utf-8"))
        status = str(payload.get("status") or "failed")
        started_at = _parse_datetime(payload.get("started_at"))
        completed_at = _parse_datetime(payload.get("completed_at"))
        error = payload.get("error")
        venv_path_text = payload.get("venv_path")
        python_path_text = payload.get("python_executable")
        packages_file = payload.get("packages_file")
        install_log = payload.get("install_log")
        hooks_file = payload.get("hooks_file") or self._HOOKS_FILENAME

        packages_path = _resolve_relative(activation_dir, packages_file)
        install_log_path = _resolve_relative(activation_dir, install_log)
        hooks_path = _resolve_relative(activation_dir, hooks_file)
        annotations: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        if hooks_path and hooks_path.exists():
            try:
                hooks_payload = json.loads(hooks_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                hooks_payload = {}
            annotations = _ensure_dict_list(hooks_payload.get("annotations"))
            diagnostics = _ensure_dict_list(hooks_payload.get("diagnostics"))

        venv_info_path = activation_dir / self._VENV_INFO_FILENAME
        if venv_info_path.exists():
            try:
                info = json.loads(venv_info_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                info = {}
            venv_path_text = venv_path_text or info.get("venv_path")
            python_path_text = python_path_text or info.get("python_executable")

        venv_path = Path(venv_path_text).resolve() if venv_path_text else None
        python_path = Path(python_path_text).resolve() if python_path_text else None

        return ActivationMetadata(
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            error=error,
            venv_path=venv_path,
            python_executable=python_path,
            packages_path=packages_path,
            install_log_path=install_log_path,
            hooks_path=hooks_path,
            annotations=annotations,
            diagnostics=diagnostics,
        )


class ActivationEnvironmentManager:
    """Create per-version virtual environments and execute activation hooks."""

    _INSTALL_LOG = "install.log"
    _PACKAGES_FILE = "packages.txt"

    def __init__(
        self,
        *,
        settings: Settings,
        storage: ConfigStorage,
        metadata_store: ActivationMetadataStore,
    ) -> None:
        self._settings = settings
        self._storage = storage
        self._metadata_store = metadata_store
        self._venv_root = settings.activation_envs_dir or (settings.storage_data_dir / "venvs")
        self._venv_root = Path(self._venv_root).resolve()
        self._venv_root.mkdir(parents=True, exist_ok=True)

    async def ensure_environment(
        self,
        *,
        config: Config,
        version: ConfigVersion,
        manifest: ManifestV1,
    ) -> ActivationMetadata:
        existing = self._metadata_store.load(config_id=config.id, version=version)
        if existing and existing.ready:
            return existing

        try:
            await self._build_environment(config=config, version=version, manifest=manifest)
        except ActivationError:
            # Result.json already written by _build_environment; re-raise for caller handling.
            raise
        except Exception as exc:  # pragma: no cover - defensive safety net
            raise ActivationError(str(exc)) from exc

        refreshed = self._metadata_store.load(config_id=config.id, version=version)
        if refreshed is None:
            raise ActivationError("Activation metadata missing after environment build")
        if not refreshed.ready:
            raise ActivationError("Activation completed but environment is not ready")
        return refreshed

    async def _build_environment(
        self,
        *,
        config: Config,
        version: ConfigVersion,
        manifest: ManifestV1,
    ) -> None:
        activation_dir = self._storage.activation_dir(config.id, version.sequence)
        if activation_dir.exists():
            shutil.rmtree(activation_dir, ignore_errors=True)
        activation_dir.mkdir(parents=True, exist_ok=True)

        venv_path = self._venv_root / version.id
        if venv_path.exists():
            shutil.rmtree(venv_path, ignore_errors=True)

        builder = venv.EnvBuilder(with_pip=True, clear=True, system_site_packages=True)
        builder.create(venv_path)
        python_path = _venv_python_path(venv_path)
        if not python_path.exists():
            raise ActivationError("Virtual environment python executable missing")

        started_at = utc_now()
        status = "succeeded"
        error_message: str | None = None
        diagnostics: list[dict[str, Any]] = []

        install_log_path = activation_dir / self._INSTALL_LOG
        packages_path = activation_dir / self._PACKAGES_FILE
        hooks_path = activation_dir / ActivationMetadataStore._HOOKS_FILENAME
        result_path = activation_dir / ActivationMetadataStore._RESULT_FILENAME
        venv_info_path = activation_dir / ActivationMetadataStore._VENV_INFO_FILENAME

        venv_info_path.write_text(
            json.dumps(
                {
                    "venv_path": str(venv_path),
                    "python_executable": str(python_path),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        package_dir = Path(version.package_path).resolve()
        requirements_path = package_dir / "requirements.txt"

        try:
            await self._install_requirements(
                python_path=python_path,
                requirements_path=requirements_path,
                log_path=install_log_path,
            )
            await self._snapshot_packages(python_path=python_path, output_path=packages_path)
            if manifest.hooks.on_activate:
                diagnostics = await self._run_activate_hooks(
                    python_path=python_path,
                    package_dir=package_dir,
                    manifest_path=package_dir / "manifest.json",
                    hooks_path=hooks_path,
                )
            else:
                hooks_path.write_text(
                    json.dumps({"annotations": [], "diagnostics": []}, indent=2),
                    encoding="utf-8",
                )
        except ActivationError as exc:
            status = "failed"
            error_message = str(exc)
            diagnostics = list(exc.diagnostics)
            raise
        except Exception as exc:  # pragma: no cover - defensive
            status = "failed"
            error_message = str(exc)
            raise ActivationError(str(exc)) from exc
        finally:
            completed_at = utc_now()
            result_payload = {
                "status": status,
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "error": error_message,
                "venv_path": str(venv_path),
                "python_executable": str(python_path),
                "packages_file": packages_path.name if packages_path.exists() else None,
                "install_log": install_log_path.name if install_log_path.exists() else None,
                "hooks_file": hooks_path.name if hooks_path.exists() else None,
                "diagnostics": diagnostics,
            }
            result_path.write_text(json.dumps(result_payload, indent=2), encoding="utf-8")

    async def _install_requirements(
        self,
        *,
        python_path: Path,
        requirements_path: Path,
        log_path: Path,
    ) -> None:
        if not requirements_path.exists():
            log_path.write_text("requirements.txt not present; skipping install.\n", encoding="utf-8")
            return

        command = [
            str(python_path),
            "-m",
            "pip",
            "install",
            "--no-input",
            "--disable-pip-version-check",
            "--require-virtualenv",
            "-r",
            str(requirements_path),
        ]
        returncode, stdout, stderr = await _run_subprocess(command)
        log_path.write_text(stdout + stderr, encoding="utf-8")
        if returncode != 0:
            raise ActivationError(
                "Dependency installation failed",
                diagnostics=[
                    {
                        "level": "error",
                        "code": "activation.install.failed",
                        "message": "pip install returned non-zero status",
                        "hint": log_path.as_posix(),
                    }
                ],
            )

    async def _snapshot_packages(self, *, python_path: Path, output_path: Path) -> None:
        command = [str(python_path), "-m", "pip", "freeze"]
        returncode, stdout, stderr = await _run_subprocess(command)
        output_path.write_text(stdout or "", encoding="utf-8")
        if returncode != 0:
            raise ActivationError(
                "Failed to capture installed packages",
                diagnostics=[
                    {
                        "level": "error",
                        "code": "activation.freeze.failed",
                        "message": stderr.strip() or "pip freeze returned non-zero status",
                    }
                ],
            )

    async def _run_activate_hooks(
        self,
        *,
        python_path: Path,
        package_dir: Path,
        manifest_path: Path,
        hooks_path: Path,
    ) -> list[dict[str, Any]]:
        command = [
            str(python_path),
            "-m",
            "backend.app.features.configs.activation_worker",
            "--config-dir",
            str(package_dir),
            "--manifest-path",
            str(manifest_path),
            "--output",
            str(hooks_path),
        ]
        returncode, stdout, stderr = await _run_subprocess(command)
        if not hooks_path.exists():
            hooks_path.write_text(
                json.dumps({"annotations": [], "diagnostics": []}, indent=2),
                encoding="utf-8",
            )

        diagnostics: list[dict[str, Any]] = []
        if returncode != 0:
            try:
                hooks_payload = json.loads(hooks_path.read_text(encoding="utf-8"))
                diagnostics = _ensure_dict_list(hooks_payload.get("diagnostics"))
            except json.JSONDecodeError:
                diagnostics = []
            if stderr.strip():
                diagnostics.append(
                    {
                        "level": "error",
                        "code": "activation.hooks.stderr",
                        "message": stderr.strip(),
                    }
                )
            raise ActivationError("on_activate hooks failed", diagnostics=diagnostics)

        if not diagnostics:
            try:
                hooks_payload = json.loads(hooks_path.read_text(encoding="utf-8"))
                diagnostics = _ensure_dict_list(hooks_payload.get("diagnostics"))
            except json.JSONDecodeError:
                diagnostics = []

        return diagnostics


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _resolve_relative(base: Path, filename: str | None) -> Path | None:
    if not filename:
        return None
    return (base / filename).resolve()


def _ensure_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for entry in value:
        if isinstance(entry, dict):
            items.append(entry)
    return items


def _venv_python_path(venv_path: Path) -> Path:
    if os.name == "nt":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


async def _run_subprocess(command: list[str]) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    return process.returncode or 0, stdout, stderr
