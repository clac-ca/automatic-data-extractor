"""Data structures shared across ade_engine modules.

These are intentionally lightweight so the package can be imported (and
installed) before the rest of the runtime is implemented.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EngineMetadata:
    """Describes the installed ade_engine distribution."""

    name: str = "ade-engine"
    version: str = "0.0.0"
    description: str | None = None


__all__ = ["EngineMetadata"]
