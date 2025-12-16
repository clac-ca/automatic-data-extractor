"""Stable build fingerprinting for ADE configuration environments."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ade_api.common.encoding import json_dumps

__all__ = ["compute_build_fingerprint", "compute_engine_source_digest"]


def compute_engine_source_digest(engine_spec: str) -> str | None:
    """Return a deterministic digest for an on-disk engine source tree.

    This is intended for development environments where ``engine_spec`` points
    at a local directory (e.g. ``apps/ade-engine``) and the engine version may
    not be bumped for every code change.
    """

    root = Path(engine_spec)
    if not (root.exists() and root.is_dir()):
        return None

    candidates: list[Path] = []
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        candidates.append(pyproject)

    src_root = root / "src"
    if src_root.exists():
        candidates.extend(src_root.rglob("*.py"))

    if not candidates:
        return None

    digest = hashlib.sha256()
    for path in sorted({p.resolve() for p in candidates}):
        try:
            rel = path.relative_to(root.resolve()).as_posix()
        except ValueError:
            # Not under root (shouldn't happen), still keep it deterministic.
            rel = path.as_posix()
        try:
            data = path.read_bytes()
        except OSError:
            # If a file disappears during a run (rare), fall back to metadata.
            stat = path.stat() if path.exists() else None
            data = f"{stat.st_size if stat else 0}:{stat.st_mtime_ns if stat else 0}".encode()

        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")

    return digest.hexdigest()


def compute_build_fingerprint(
    *,
    config_digest: str,
    engine_spec: str,
    engine_version: str | None,
    python_version: str | None,
    python_bin: str | None,
    extra: Mapping[str, Any] | None = None,
) -> str:
    """Return a deterministic fingerprint string for a build specification."""

    payload = {
        "config_digest": config_digest,
        "engine_spec": engine_spec,
        "engine_version": engine_version,
        "python_version": python_version,
        "python_bin": python_bin,
        "extra": extra or {},
    }
    normalized = json_dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()
