"""Helpers for reading installed package versions."""

from __future__ import annotations

import json
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

DEFAULT_WEB_VERSION_FILE = Path("/usr/share/nginx/html/version.json")

__all__ = ["installed_version", "read_web_version"]


def installed_version(*dist_names: str) -> str:
    """Return the first installed distribution version or ``unknown``."""

    for name in dist_names:
        try:
            return version(name)
        except PackageNotFoundError:
            continue
    return "unknown"


def read_web_version(path: Path | str | None = None) -> str:
    """Return the web UI version from a version.json file, or ``unknown``."""

    if path is None:
        env_value = os.getenv("ADE_WEB_VERSION_FILE")
        path = Path(env_value) if env_value else DEFAULT_WEB_VERSION_FILE
    else:
        path = Path(path)

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "unknown"
    except OSError:
        return "unknown"

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return "unknown"

    if isinstance(payload, dict):
        value = payload.get("version")
        if isinstance(value, str) and value.strip():
            return value.strip()

    return "unknown"
