"""Config loader entrypoint used by the engine."""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from types import ModuleType
from importlib import resources
from pathlib import Path

from pydantic import ValidationError

from ade_engine.config.column_registry import ColumnRegistry
from ade_engine.config.hook_registry import HookRegistry
from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.errors import ConfigError
from ade_engine.schemas.manifest import ManifestV1


@dataclass
class ConfigRuntime:
    """Aggregate of manifest context and runtime registries."""

    package: ModuleType
    manifest: ManifestContext
    columns: ColumnRegistry
    hooks: HookRegistry


def _load_manifest(package: str, manifest_path: Path | None) -> ManifestContext:
    try:
        pkg = importlib.import_module(package)
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised via ConfigError
        raise ConfigError(f"Config package '{package}' could not be imported") from exc

    resolved_path = Path(manifest_path) if manifest_path else Path(resources.files(pkg) / "manifest.json")
    if not resolved_path.exists():
        raise ConfigError(f"Manifest file not found at '{resolved_path}'")

    try:
        raw_json = json.loads(resolved_path.read_text())
    except json.JSONDecodeError as exc:  # pragma: no cover - exercised via ConfigError
        raise ConfigError(f"Manifest at '{resolved_path}' is not valid JSON: {exc}") from exc
    except OSError as exc:  # pragma: no cover - exercised via ConfigError
        raise ConfigError(f"Unable to read manifest file '{resolved_path}'") from exc

    try:
        model = ManifestV1.model_validate(raw_json)
    except ValidationError as exc:  # pragma: no cover - exercised via ConfigError
        raise ConfigError(f"Manifest validation failed: {exc}") from exc

    return ManifestContext(raw_json=raw_json, model=model)


def load_config_runtime(package: str = "ade_config", manifest_path: Path | None = None) -> ConfigRuntime:
    """Load manifest and registries for the given config package."""

    manifest = _load_manifest(package, manifest_path)
    pkg = importlib.import_module(package)

    columns = ColumnRegistry.from_manifest(package=pkg, fields=manifest.columns.fields)
    hooks = HookRegistry.from_manifest(package=pkg, manifest=manifest)

    return ConfigRuntime(package=pkg, manifest=manifest, columns=columns, hooks=hooks)


__all__ = ["ConfigRuntime", "load_config_runtime"]
