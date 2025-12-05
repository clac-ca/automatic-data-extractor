"""Simple data-row detector for sandbox tables."""

from __future__ import annotations

from typing import Any


def detect_non_empty_data_rows(
    *,
    row_index: int,
    row_values: list[Any],
    logger: Any | None = None,
    event_emitter: Any | None = None,
    **_: Any,
) -> dict[str, float]:
    """Mark rows after the header that contain data."""

    if row_index <= 1:
        return {"data": 0.0}

    if not any(value not in (None, "") for value in row_values):
        return {"data": 0.0}

    return {"data": 1.0}
