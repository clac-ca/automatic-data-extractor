"""NDJSON persistence helpers for ADE events.

This module is intentionally tiny and dependency-free so features can share
consistent event file behavior without duplicating the same file I/O code.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ade_api.infra.events.utils import ensure_event_defaults
from ade_api.schemas.events import AdeEvent

__all__ = ["append_line", "iter_events_file"]


def append_line(path: Path, line: str) -> None:
    """Append one UTF-8 line to ``path`` (creating parent directories)."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.write("\n")


def iter_events_file(path: Path, *, after_sequence: int | None = None) -> Iterable[AdeEvent]:
    """Iterate events from a NDJSON file.

    Empty lines are ignored. ``after_sequence`` filters out events whose
    ``sequence`` is <= that value.
    """

    if not path.exists():
        return []

    def _iter() -> Iterable[AdeEvent]:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                event = ensure_event_defaults(AdeEvent.model_validate_json(raw))
                if after_sequence is not None and event.sequence is not None and event.sequence <= after_sequence:
                    continue
                yield event

    return _iter()
