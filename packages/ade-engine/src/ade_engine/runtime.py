"""Runtime helpers for :mod:`ade_engine`."""

from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, ValidationError

from .schemas.models import ManifestContext, ManifestV1


class ManifestNotFoundError(RuntimeError):
    """Raised when the ade_config manifest cannot be located."""


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # pragma: no cover - defensive guard
        raise ManifestNotFoundError(f"Manifest not found at {path}") from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - malformed manifest
        raise ManifestNotFoundError(f"Manifest is not valid JSON: {path}") from exc


def load_config_manifest(
    *,
    package: str = "ade_config",
    resource: str = "manifest.json",
    manifest_path: Path | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Return the ade_config manifest as a dict.

    When ``manifest_path`` is supplied (mainly for tests/CLI overrides), the
    manifest is read directly from that path. Otherwise, the function attempts to
    load ``resource`` from the installed ``package`` via importlib.resources.
    """

    if manifest_path is not None:
        manifest = _read_manifest(manifest_path)
    else:
        try:
            resource_path = resources.files(package) / resource
        except ModuleNotFoundError as exc:
            raise ManifestNotFoundError(
                f"Config package '{package}' cannot be imported."
            ) from exc

        if not resource_path.is_file():
            raise ManifestNotFoundError(
                f"Resource '{resource}' not found in '{package}'."
            )
        manifest = _read_manifest(Path(resource_path))

    if validate:
        _validate_manifest(manifest)

    return manifest


def load_manifest_context(
    *,
    package: str = "ade_config",
    resource: str = "manifest.json",
    manifest_path: Path | None = None,
) -> ManifestContext:
    """Return a :class:`ManifestContext` with schema-derived helpers."""

    manifest = load_config_manifest(
        package=package,
        resource=resource,
        manifest_path=manifest_path,
        validate=True,
    )
    version = _manifest_version(manifest)
    model = None
    if version and version.startswith("ade.manifest/v1"):
        model = ManifestV1.model_validate(manifest)
    return ManifestContext(raw=manifest, version=version, model=model)


def resolve_jobs_root(
    jobs_dir: Path | None = None, *, env: Mapping[str, str] | None = None
) -> Path:
    """Return the base directory for job execution.

    The resolution order matches the developer documentation: explicit arguments
    win, followed by ``ADE_JOBS_DIR`` and finally ``ADE_DATA_DIR``.
    """

    env = os.environ if env is None else env

    if jobs_dir is not None:
        return Path(jobs_dir)

    if env.get("ADE_JOBS_DIR"):
        return Path(env["ADE_JOBS_DIR"])

    data_dir = Path(env.get("ADE_DATA_DIR", "./data"))
    return data_dir / "jobs"


def _load_manifest_schema() -> dict[str, Any]:
    schema_resource = resources.files("ade_engine.schemas") / "manifest.v1.schema.json"
    return json.loads(schema_resource.read_text(encoding="utf-8"))


_MANIFEST_VALIDATOR = Draft202012Validator(_load_manifest_schema())


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    schema_tag = _manifest_version(manifest)
    if schema_tag and schema_tag.startswith("ade.manifest/v1"):
        try:
            _MANIFEST_VALIDATOR.validate(manifest)
        except ValidationError as exc:  # pragma: no cover - jsonschema formats message
            raise ManifestNotFoundError(f"Manifest failed validation: {exc.message}") from exc
        return

    _validate_legacy_manifest(manifest)


def _manifest_version(manifest: Mapping[str, Any]) -> str | None:
    if isinstance(manifest.get("info"), Mapping):
        schema_value = manifest["info"].get("schema")
        if isinstance(schema_value, str):
            return schema_value
    schema_version = manifest.get("schema_version")
    if isinstance(schema_version, str):
        return schema_version.replace("@", "/")
    return None


def _validate_legacy_manifest(manifest: Mapping[str, Any]) -> None:
    required_top_level = {"schema_version", "script_api", "engine", "columns"}
    missing = sorted(value for value in required_top_level if value not in manifest)
    if missing:
        raise ManifestNotFoundError(
            "Manifest missing required keys: " + ", ".join(missing)
        )

    columns = manifest.get("columns", {})
    if "order" not in columns or "meta" not in columns:
        raise ManifestNotFoundError("Manifest columns section must define 'order' and 'meta'")


__all__ = [
    "ManifestContext",
    "ManifestNotFoundError",
    "load_config_manifest",
    "load_manifest_context",
    "resolve_jobs_root",
]
