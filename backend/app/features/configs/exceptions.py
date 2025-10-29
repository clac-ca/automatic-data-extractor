"""Domain exceptions for configuration engine v0.4 (to be implemented)."""

from __future__ import annotations


class ConfigError(RuntimeError):
    """Base error for configuration engine failures."""


__all__ = ["ConfigError"]
