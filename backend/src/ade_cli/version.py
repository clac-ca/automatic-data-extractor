"""ADE version metadata."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path


def _read_version() -> str:
    try:
        return metadata.version("automatic-data-extractor")
    except metadata.PackageNotFoundError:
        pass
    try:
        return (Path(__file__).resolve().parents[3] / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


__version__ = _read_version()
