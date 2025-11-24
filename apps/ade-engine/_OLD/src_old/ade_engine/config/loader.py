"""Manifest and environment resolution helpers."""

from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, ValidationError

from ade_engine.core.manifest import ManifestContext, ManifestV1


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


def _manifest_version(manifest: Mapping[str, Any]) -> str | None:
    if isinstance(manifest.get("info"), Mapping):
        schema_value = manifest["info"].get("schema")
        if isinstance(schema_value, str):
            return schema_value
    return None


def _load_manifest_schema() -> dict[str, Any]:
    schema_resource = resources.files("ade_engine.schemas") / "manifest.v1.schema.json"
    return json.loads(schema_resource.read_text(encoding="utf-8"))


_MANIFEST_VALIDATOR = Draft202012Validator(_load_manifest_schema())


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    schema_tag = _manifest_version(manifest)
    if not schema_tag:
        raise ManifestNotFoundError("Manifest missing required info.schema version tag")
    if not schema_tag.startswith("ade.manifest/v1"):
        raise ManifestNotFoundError(f"Unsupported manifest schema: {schema_tag}")
    try:
        _MANIFEST_VALIDATOR.validate(manifest)
    except ValidationError as exc:  # pragma: no cover - jsonschema formats message
        raise ManifestNotFoundError(f"Manifest failed validation: {exc.message}") from exc


def load_manifest(
    *,
    package: str = "ade_config",
    resource: str = "manifest.json",
    manifest_path: Path | None = None,
) -> ManifestContext:
    """Read, validate, and parse a manifest into a ManifestContext."""

    if manifest_path is not None:
        manifest = _read_manifest(manifest_path)
    else:
        try:
            resource_path = resources.files(package) / resource
        except ModuleNotFoundError as exc:
            raise ManifestNotFoundError(f"Config package '{package}' cannot be imported.") from exc
        else:
            if not resource_path.is_file():
                raise ManifestNotFoundError(f"Resource '{resource}' not found in '{package}'.")
            manifest = _read_manifest(Path(resource_path))

    _validate_manifest(manifest)

    model = ManifestV1.model_validate(manifest)
    return ManifestContext(
        raw=manifest,
        version=_manifest_version(manifest),
        model=model,
    )


def resolve_jobs_root(
    jobs_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the jobs root using explicit args, ADE_JOBS_DIR, or ADE_DATA_DIR."""

    env = os.environ if env is None else env

    if jobs_dir is not None:
        return Path(jobs_dir)

    if env.get("ADE_JOBS_DIR"):
        return Path(env["ADE_JOBS_DIR"])

    data_dir = Path(env.get("ADE_DATA_DIR", "./data"))
    return data_dir / "jobs"


def resolve_input_sheets(env: Mapping[str, str] | None = None) -> list[str] | None:
    """Normalize sheet selection from ADE_RUN_INPUT_SHEET(S) env vars."""

    env = os.environ if env is None else env

    sheets_raw = env.get("ADE_RUN_INPUT_SHEETS")
    if sheets_raw:
        parsed: Any
        try:
            parsed = json.loads(sheets_raw)
        except json.JSONDecodeError:
            parsed = sheets_raw
        candidates: list[str] = []
        if isinstance(parsed, list):
            candidates = [str(value) for value in parsed]
        elif isinstance(parsed, str):
            candidates = [part for part in parsed.split(",")]
        cleaned = [value.strip() for value in candidates if str(value).strip()]
        if cleaned:
            return cleaned

    single_sheet = env.get("ADE_RUN_INPUT_SHEET")
    if single_sheet:
        cleaned = str(single_sheet).strip()
        if cleaned:
            return [cleaned]

    return None


__all__ = [
    "ManifestNotFoundError",
    "load_manifest",
    "resolve_input_sheets",
    "resolve_jobs_root",
]
