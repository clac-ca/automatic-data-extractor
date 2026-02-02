"""Workspace settings helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

WORKSPACE_PROCESSING_PAUSED_KEY = "processing_paused"


def read_processing_paused(settings: Mapping[str, Any] | None) -> bool:
    if not settings:
        return False
    return bool(settings.get(WORKSPACE_PROCESSING_PAUSED_KEY, False))


def apply_processing_paused(
    settings: Mapping[str, Any] | None,
    paused: bool | None,
) -> dict[str, Any]:
    payload = dict(settings or {})
    if paused is not None:
        payload[WORKSPACE_PROCESSING_PAUSED_KEY] = bool(paused)
    return payload


__all__ = [
    "WORKSPACE_PROCESSING_PAUSED_KEY",
    "apply_processing_paused",
    "read_processing_paused",
]
