"""Config loader entrypoint used by the engine."""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from types import ModuleType

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - fallback for older interpreters
    import tomli as tomllib  # type: ignore

from pydantic import ValidationError

from ade_engine.config.columns import ColumnRegistry
from ade_engine.config.hooks import HookRegistry
from ade_engine.config.manifest import ManifestContext
from ade_engine.core.errors import ConfigError
from ade_engine.schemas.manifest import ManifestV1


@dataclass
class ConfigRuntime:
    """Aggregate of manifest context and runtime registries."""

    package: ModuleType
    manifest: ManifestContext
    columns: ColumnRegistry
    hooks: HookRegistry


def resolve_config_package(config_package: str | None) -> tuple[str, Path | None]:
    """Normalize a config package reference (module name or path).

    Returns the importable package name and an optional sys.path entry that
    should be added before importing.
    """

    package_value = config_package or "ade_config"
    candidate_path = Path(package_value)
    if not candidate_path.exists():
        return package_value, None

    if candidate_path.is_file():
        msg = f"Config package path must be a directory, got file '{candidate_path}'"
        raise ConfigError(msg)

    package_dirs = [
        candidate_path if candidate_path.name == "ade_config" else None,
        candidate_path / "ade_config",
        candidate_path / "src" / "ade_config",
    ]

    for pkg_dir in package_dirs:
        if pkg_dir is None:
            continue
        manifest_json = pkg_dir / "manifest.json"
        manifest_toml = pkg_dir / "manifest.toml"
        if manifest_toml.exists() or manifest_json.exists():
            return pkg_dir.name, pkg_dir.parent

    raise ConfigError(
        "Unable to locate manifest.toml/manifest.json under config path "
        f"'{candidate_path}'. Expected it in 'ade_config/manifest.toml' (or manifest.json) or 'src/ade_config/'."
    )


def _load_manifest(package: str, manifest_path: Path | None) -> ManifestContext:
    try:
        pkg = importlib.import_module(package)
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised via ConfigError
        raise ConfigError(f"Config package '{package}' could not be imported") from exc

    default_manifest = Path(resources.files(pkg) / "manifest.toml")
    fallback_manifest = Path(resources.files(pkg) / "manifest.json")
    resolved_path = Path(manifest_path) if manifest_path else (default_manifest if default_manifest.exists() else fallback_manifest)
    if not resolved_path.exists():
        raise ConfigError(f"Manifest file not found at '{resolved_path}'")

    try:
        if resolved_path.suffix.lower() == ".toml":
            raw_manifest = tomllib.loads(resolved_path.read_text())
        else:
            raw_manifest = json.loads(resolved_path.read_text())
    except (tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:  # pragma: no cover - exercised via ConfigError
        raise ConfigError(f"Manifest at '{resolved_path}' is not valid TOML/JSON: {exc}") from exc
    except OSError as exc:  # pragma: no cover - exercised via ConfigError
        raise ConfigError(f"Unable to read manifest file '{resolved_path}'") from exc

    try:
        model = ManifestV1.model_validate(raw_manifest)
    except ValidationError as exc:  # pragma: no cover - exercised via ConfigError
        raise ConfigError(f"Manifest validation failed: {exc}") from exc

    return ManifestContext(raw_json=raw_manifest, model=model)


def load_config_runtime(package: str = "ade_config", manifest_path: Path | None = None) -> ConfigRuntime:
    """Load manifest and registries for the given config package."""

    normalized_package, sys_path = resolve_config_package(package)
    if sys_path:
        sys_path_entry = str(sys_path)
        if sys_path_entry not in sys.path:
            sys.path.insert(0, sys_path_entry)

    manifest = _load_manifest(normalized_package, manifest_path)
    if manifest.model.script_api_version != 3:
        raise ConfigError(
            f"Config manifest declares script_api_version={manifest.model.script_api_version}; "
            "this version of ade_engine requires script_api_version=3 and the new workbook/sheet/table hook lifecycle."
        )
    pkg = importlib.import_module(normalized_package)

    columns = ColumnRegistry.from_manifest(package=pkg, fields=manifest.columns.fields)
    hooks = HookRegistry.from_manifest(package=pkg, manifest=manifest)

    return ConfigRuntime(package=pkg, manifest=manifest, columns=columns, hooks=hooks)


__all__ = ["ConfigRuntime", "load_config_runtime", "resolve_config_package"]
