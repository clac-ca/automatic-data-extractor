"""Stable build fingerprinting for ADE configuration environments."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from ade_api.common.encoding import json_dumps

__all__ = ["compute_build_fingerprint"]


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
