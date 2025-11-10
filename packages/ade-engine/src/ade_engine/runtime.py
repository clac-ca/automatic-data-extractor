"""Placeholder runtime helpers for ade_engine."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any


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
) -> dict[str, Any]:
    """Return the ade_config manifest as a dict.

    When ``manifest_path`` is supplied (mainly for tests/CLI overrides), the
    manifest is read directly from that path. Otherwise, the function attempts to
    load ``resource`` from the installed ``package`` via importlib.resources.
    """

    if manifest_path is not None:
        return _read_manifest(manifest_path)

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
    return _read_manifest(Path(resource_path))


__all__ = ["ManifestNotFoundError", "load_config_manifest"]
