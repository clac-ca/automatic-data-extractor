"""Helpers for dependency-only digests used to decide venv rebuilds."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from .constants import CONFIG_DEP_FILES


def compute_dependency_digest(root: Path) -> str:
    """Hash only dependency manifests inside a config package.

    Venv rebuilds are expensive; we only need to redo them when dependency
    metadata changes. This digest intentionally ignores source files so code
    edits picked up via editable installs do not force a rebuild.
    """

    digest = sha256()
    found = False

    for name in CONFIG_DEP_FILES:
        path = root / name
        if not path.is_file():
            continue
        found = True
        digest.update(name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())

    if not found:
        # Fallback: if no manifest exists, treat as empty dependencies so the
        # fingerprint remains stable but still deterministic.
        digest.update(b"empty")

    return f"sha256:{digest.hexdigest()}"


__all__ = ["compute_dependency_digest"]
