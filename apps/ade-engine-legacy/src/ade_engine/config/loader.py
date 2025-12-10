"""Config loader entrypoint used by the engine."""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from types import ModuleType

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from pydantic import ValidationError

from ade_engine.config.columns import ColumnRegistry
from ade_engine.config.hooks import HooksRuntime
from ade_engine.config.manifest import ManifestContext
from ade_engine.config.row_detectors import RowDetector, discover_row_detectors
from ade_engine.exceptions import ConfigError
from ade_engine.schemas.manifest import ManifestV1

_MANIFEST_FILE = "manifest.toml"
_REQUIRED_SCRIPT_API_VERSION = 3


@dataclass(frozen=True)
class ConfigRuntime:
    """Aggregate of manifest context and resolved plugin callables."""

    package: ModuleType
    manifest: ManifestContext
    columns: ColumnRegistry
    hooks: HooksRuntime
    row_detectors: tuple[RowDetector, ...]


@dataclass(frozen=True)
class ResolvedConfigPackage:
    """Normalized reference to a config package.

    - ``package`` is the importable module name.
    - ``sys_path`` is a directory to prepend to ``sys.path`` (if needed) before importing.
    """

    package: str
    sys_path: Path | None = None

    def ensure_on_sys_path(self) -> None:
        if self.sys_path is None:
            return
        entry = str(self.sys_path)
        if entry not in sys.path:
            sys.path.insert(0, entry)


def resolve_config_package(config_package: str | None) -> ResolvedConfigPackage:
    """Normalize a config package reference (module name or filesystem path)."""

    value = config_package or "ade_config"
    candidate_path = Path(value)

    # Not a filesystem path -> treat as importable module name.
    if not candidate_path.exists():
        return ResolvedConfigPackage(package=value, sys_path=None)

    if candidate_path.is_file():
        raise ConfigError(f"Config package path must be a directory, got file '{candidate_path}'")

    # Accept:
    #   <path>/ade_config/manifest.toml
    #   <path>/src/ade_config/manifest.toml
    #   <path> where <path>.name == "ade_config"
    candidates = [
        candidate_path if candidate_path.name == "ade_config" else None,
        candidate_path / "ade_config",
        candidate_path / "src" / "ade_config",
    ]

    for pkg_dir in candidates:
        if pkg_dir is None:
            continue

        manifest_toml = pkg_dir / _MANIFEST_FILE
        if manifest_toml.exists():
            return ResolvedConfigPackage(package=pkg_dir.name, sys_path=pkg_dir.parent)

        manifest_json = pkg_dir / "manifest.json"
        if manifest_json.exists():
            raise ConfigError(
                "manifest.json found; manifest.toml is now required. "
                f"Convert the manifest to TOML and save it as '{_MANIFEST_FILE}'."
            )

    raise ConfigError(
        "Unable to locate manifest.toml under config path "
        f"'{candidate_path}'. Expected it in 'ade_config/{_MANIFEST_FILE}' or 'src/ade_config/{_MANIFEST_FILE}'."
    )


def _load_manifest(package: str, manifest_path: Path | None) -> ManifestContext:
    try:
        pkg = importlib.import_module(package)
    except ModuleNotFoundError as exc:
        raise ConfigError(f"Config package '{package}' could not be imported") from exc

    def _load_from_path(path: Path) -> ManifestContext:
        if not path.exists():
            raise ConfigError(f"Manifest file not found at '{path}'")
        if path.suffix.lower() != ".toml":
            raise ConfigError(f"Manifest must be a TOML file, got '{path.name}'")

        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"Manifest at '{path}' is not valid TOML: {exc}") from exc
        except OSError as exc:
            raise ConfigError(f"Unable to read manifest file '{path}'") from exc

        try:
            model = ManifestV1.model_validate(raw)
        except ValidationError as exc:
            raise ConfigError(f"Manifest validation failed: {exc}") from exc

        return ManifestContext(raw=raw, model=model)

    manifest_resource = resources.files(pkg).joinpath(_MANIFEST_FILE)
    if manifest_path:
        return _load_from_path(Path(manifest_path))

    with resources.as_file(manifest_resource) as default_manifest_path:
        return _load_from_path(default_manifest_path)


def load_config_runtime(
    package: str | ResolvedConfigPackage = "ade_config",
    manifest_path: Path | None = None,
) -> ConfigRuntime:
    """Load manifest and resolved plugin callables for the given config package."""

    resolved = package if isinstance(package, ResolvedConfigPackage) else resolve_config_package(package)
    resolved.ensure_on_sys_path()

    manifest = _load_manifest(resolved.package, manifest_path)
    if manifest.model.script_api_version != _REQUIRED_SCRIPT_API_VERSION:
        raise ConfigError(
            f"Config manifest declares script_api_version={manifest.model.script_api_version}; "
            f"this ade_engine build requires script_api_version={_REQUIRED_SCRIPT_API_VERSION}."
        )

    pkg = importlib.import_module(resolved.package)

    return ConfigRuntime(
        package=pkg,
        manifest=manifest,
        columns=ColumnRegistry.from_manifest(package=pkg, fields=manifest.columns),
        hooks=HooksRuntime.from_manifest(package=pkg, manifest=manifest),
        row_detectors=discover_row_detectors(pkg),
    )


__all__ = ["ConfigRuntime", "ResolvedConfigPackage", "load_config_runtime", "resolve_config_package"]
