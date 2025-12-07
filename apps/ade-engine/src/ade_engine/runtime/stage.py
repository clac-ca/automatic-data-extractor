"""Small helper for tracking the current engine stage for error reporting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StageTracker:
    value: str = "prepare"

    def set(self, value: str) -> None:
        self.value = value


__all__ = ["StageTracker"]
