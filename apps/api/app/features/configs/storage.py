"""Filesystem helper for config packages."""

from __future__ import annotations

import json
import secrets
import shutil
import tomllib
from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path

from fastapi.concurrency import run_in_threadpool

from .exceptions import (
    ConfigPublishConflictError,
    ConfigSourceInvalidError,
    ConfigSourceNotFoundError,
    ConfigStorageNotFoundError,
)
from .schemas import ConfigValidationIssue

_DIGEST_SUFFIXES = {".py", ".toml", ".json"}
_COPY_IGNORE_PATTERNS = (
    ".git",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    "*.pyc",
    ".DS_Store",
    "dist",
    "build",
)


class ConfigStorage:
    """Manage filesystem copies and validation for configurations."""

    def __init__(self, *, templates_root: Path, configs_root: Path) -> None:
        self._templates_root = templates_root.expanduser().resolve()
        self._configs_root = configs_root.expanduser().resolve()

    def workspace_root(self, workspace_id: str) -> Path:
        return self._configs_root / workspace_id / "config_packages"

    def config_path(self, workspace_id: str, config_id: str) -> Path:
        return self.workspace_root(workspace_id) / config_id

    async def materialize_from_template(
        self,
        *,
        workspace_id: str,
        config_id: str,
        template_id: str,
    ) -> None:
        template_path = (self._templates_root / template_id).resolve()
        if not template_path.is_dir():
            raise ConfigSourceNotFoundError(f"Template '{template_id}' not found")
        try:
            template_path.relative_to(self._templates_root)
        except ValueError as exc:
            raise ConfigSourceNotFoundError(f"Template '{template_id}' not found") from exc
        await self._materialize_from_source(
            source=template_path,
            workspace_id=workspace_id,
            config_id=config_id,
        )

    async def materialize_from_clone(
        self,
        *,
        workspace_id: str,
        source_config_id: str,
        new_config_id: str,
    ) -> None:
        source_path = self.config_path(workspace_id, source_config_id)
        exists = await run_in_threadpool(source_path.is_dir)
        if not exists:
            raise ConfigSourceNotFoundError(
                f"Configuration '{source_config_id}' not found"
            )
        await self._materialize_from_source(
            source=source_path,
            workspace_id=workspace_id,
            config_id=new_config_id,
        )

    async def ensure_config_path(self, workspace_id: str, config_id: str) -> Path:
        path = self.config_path(workspace_id, config_id)
        exists = await run_in_threadpool(path.is_dir)
        if not exists:
            raise ConfigStorageNotFoundError(
                f"Configuration files missing for {config_id}"
            )
        return path

    async def delete_config(
        self,
        *,
        workspace_id: str,
        config_id: str,
        missing_ok: bool = True,
    ) -> None:
        path = self.config_path(workspace_id, config_id)

        def _remove() -> None:
            try:
                shutil.rmtree(path)
            except FileNotFoundError:
                if not missing_ok:
                    raise

        await run_in_threadpool(_remove)

    async def validate_path(
        self,
        path: Path,
    ) -> tuple[list[ConfigValidationIssue], str | None]:
        def _validate() -> tuple[list[ConfigValidationIssue], str | None]:
            issues: list[ConfigValidationIssue] = []
            pyproject = path / "pyproject.toml"
            manifest = path / "src" / "ade_config" / "manifest.json"

            if not pyproject.is_file():
                issues.append(
                    ConfigValidationIssue(
                        path="pyproject.toml",
                        message="pyproject.toml is required",
                    )
                )
            else:
                try:
                    tomllib.loads(pyproject.read_text(encoding="utf-8"))
                except (tomllib.TOMLDecodeError, OSError) as exc:
                    issues.append(
                        ConfigValidationIssue(
                            path="pyproject.toml",
                            message=f"pyproject.toml is invalid: {exc}",
                        )
                    )

            if not manifest.is_file():
                issues.append(
                    ConfigValidationIssue(
                        path="src/ade_config/manifest.json",
                        message="manifest.json is required within src/ade_config",
                    )
                )
            else:
                try:
                    json.loads(manifest.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError) as exc:
                    issues.append(
                        ConfigValidationIssue(
                            path="src/ade_config/manifest.json",
                            message=f"manifest.json is invalid: {exc}",
                        )
                    )

            if issues:
                return issues, None

            digest = _calculate_digest(path)
            return issues, digest

        return await run_in_threadpool(_validate)

    async def _materialize_from_source(
        self,
        *,
        source: Path,
        workspace_id: str,
        config_id: str,
    ) -> None:
        workspace_root = self.workspace_root(workspace_id)
        destination = workspace_root / config_id
        staging = workspace_root / f".staging-{config_id}-{secrets.token_hex(4)}"

        async def _copy_to_stage() -> None:
            def _copy() -> None:
                workspace_root.mkdir(parents=True, exist_ok=True)
                if staging.exists():
                    shutil.rmtree(staging)
                shutil.copytree(
                    source,
                    staging,
                    dirs_exist_ok=False,
                    ignore=shutil.ignore_patterns(*_COPY_IGNORE_PATTERNS),
                )

            await run_in_threadpool(_copy)

        await _copy_to_stage()
        try:
            issues, _ = await self.validate_path(staging)
        except Exception:
            await self._remove_path(staging)
            raise

        if issues:
            await self._remove_path(staging)
            raise ConfigSourceInvalidError(issues)

        try:
            await self._publish_stage(staging, destination)
        except Exception:
            await self._remove_path(staging)
            raise

    async def _publish_stage(self, staging: Path, destination: Path) -> None:
        def _publish() -> None:
            if destination.exists():
                raise ConfigPublishConflictError(
                    f"Destination '{destination}' already exists"
                )
            staging.replace(destination)

        await run_in_threadpool(_publish)

    async def _remove_path(self, path: Path) -> None:
        def _remove() -> None:
            shutil.rmtree(path, ignore_errors=True)

        await run_in_threadpool(_remove)


def _calculate_digest(root: Path) -> str:
    files = _collect_digest_files(root)
    digest = sha256()
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _collect_digest_files(root: Path) -> list[Path]:
    def _iter() -> Iterable[Path]:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in _DIGEST_SUFFIXES:
                yield path

    files = list(_iter())
    files.sort(key=lambda item: item.relative_to(root).as_posix())
    return files


__all__ = ["ConfigStorage"]
