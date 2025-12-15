"""Example ADE config package (registry-based).

This template favors explicit registration for clarity and determinism:

    def register(registry): ...
"""

from __future__ import annotations

from . import column_detectors, hooks, row_detectors


def register(registry) -> None:
    row_detectors.register(registry)
    column_detectors.register(registry)
    hooks.register(registry)
