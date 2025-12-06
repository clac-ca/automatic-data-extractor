"""Minimal header detector tuned for sample sandbox spreadsheets."""

from __future__ import annotations

from typing import Any


def detect_first_header_row(
    *,
    row_index: int,
    row_values: list[Any],
    logger: Any | None = None,
    event_emitter: Any | None = None,
    **_: Any,
) -> float | dict[str, float]:
    """Prefer the first non-empty row as the header."""

    if not any(value not in (None, "") for value in row_values):
        return {}

    if row_index == 1:
        return {"header": 1.0}
    if row_index <= 3:
        return {"header": 0.35}
    return {"header": 0.0}
