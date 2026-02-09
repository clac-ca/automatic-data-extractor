"""Shared filesystem helpers for configuration templates and packages."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path

# Ignore metadata and common build/IDE artifacts when copying trees.
COPY_IGNORE_PATTERNS = (
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


def copytree_no_stat(
    source: Path,
    destination: Path,
    *,
    ignore: Callable[[str, list[str]], set[str]] | None = None,
) -> None:
    """Copy a directory tree without preserving chmod/chown/utime metadata.

    Some networked volumes (e.g., SMB) reject chmod/utime, causing copy2/copytree
    to raise EPERM. This keeps the copy to simple data writes.
    """

    ignore = ignore or (lambda _src, _names: set())

    for root, dirnames, filenames in os.walk(source):
        root_path = Path(root)
        relative_root = root_path.relative_to(source)
        destination_root = destination / relative_root

        names = dirnames + filenames
        ignored = set(ignore(root, names))

        # Avoid recursing into ignored directories
        dirnames[:] = [name for name in dirnames if name not in ignored]
        destination_root.mkdir(parents=True, exist_ok=True)

        for filename in filenames:
            if filename in ignored:
                continue
            source_file = root_path / filename
            destination_file = destination_root / filename
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file, destination_file)


__all__ = ["COPY_IGNORE_PATTERNS", "copytree_no_stat"]
