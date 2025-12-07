"""Minimal engine settings (external to the manifest)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Settings:
    """External defaults; pipeline behavior comes from the config manifest."""

    config_package: str = "ade_config"
    include_patterns: Tuple[str, ...] = ("*.xlsx", "*.csv")


__all__ = ["Settings"]
