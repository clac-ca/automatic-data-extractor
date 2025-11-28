"""Pytest bootstrap to ensure package paths are importable across the monorepo."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

EXTRA_PATHS = [
    ROOT / "apps" / "ade-engine" / "tests",
    ROOT / "apps" / "ade-api" / "src",
    ROOT / "apps" / "ade-engine" / "src",
    ROOT / "apps" / "ade-engine",
]

for path in EXTRA_PATHS:
    if path.exists():
        sys.path.insert(0, str(path))
