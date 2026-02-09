"""Repository path constants used across ADE backend modules."""

from __future__ import annotations

import os
from pathlib import Path


def _resolve_repo_root() -> Path:
    override = os.getenv("ADE_REPO_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


REPO_ROOT = _resolve_repo_root()
SRC_ROOT = REPO_ROOT / "backend" / "src"
BACKEND_ROOT = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"


__all__ = ["BACKEND_ROOT", "FRONTEND_DIR", "REPO_ROOT", "SRC_ROOT"]
