"""CLI helpers for inspecting ADE configuration."""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from app import get_settings


def _serialise(value: Any) -> Any:
    if isinstance(value, SecretStr):
        raw = value.get_secret_value()
        return "********" if raw else ""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, list | tuple):
        return [_serialise(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialise(val) for key, val in value.items()}
    if hasattr(value, "model_dump"):
        return _serialise(value.model_dump())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def dump(_: argparse.Namespace) -> None:
    """Print the effective ADE configuration with secrets masked."""

    settings = get_settings()
    payload = {
        field: _serialise(getattr(settings, field))
        for field in settings.__class__.model_fields
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


__all__ = ["dump"]
