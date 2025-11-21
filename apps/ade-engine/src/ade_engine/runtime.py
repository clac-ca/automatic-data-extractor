"""Runtime helpers for :mod:`ade_engine`.

Kept as compatibility adapters; prefer :mod:`ade_engine.config.loader` helpers internally.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ade_engine.config.loader import (
    ManifestNotFoundError,
    load_manifest as _load_manifest,
    resolve_input_sheets,
    resolve_jobs_root,
)
from ade_engine.core.manifest import ManifestContext


def load_config_manifest(
    *,
    package: str = "ade_config",
    resource: str = "manifest.json",
    manifest_path: Path | None = None,
    validate: bool = True,  # kept for compatibility; always validated
) -> dict[str, Any]:
    """Return the ade_config manifest as a dict (deprecated for internal use)."""

    ctx = _load_manifest(package=package, resource=resource, manifest_path=manifest_path)
    return ctx.raw


def load_manifest_context(
    *,
    package: str = "ade_config",
    resource: str = "manifest.json",
    manifest_path: Path | None = None,
) -> ManifestContext:
    """Return a :class:`ManifestContext` with schema-derived helpers."""

    return _load_manifest(
        package=package,
        resource=resource,
        manifest_path=manifest_path,
    )


__all__ = [
    "ManifestContext",
    "ManifestNotFoundError",
    "load_config_manifest",
    "load_manifest_context",
    "resolve_input_sheets",
    "resolve_jobs_root",
]
