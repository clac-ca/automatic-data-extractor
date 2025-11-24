"""Detect simple first-name columns and normalize casing."""

from __future__ import annotations

from typing import Any

_FIELD = "first_name"


def detect_first_name(
    *,
    header: str | None,
    column_values_sample: list[Any],
    **_: Any,
) -> dict[str, dict[str, float]]:
    """Heuristic: header mentions 'first name' or 'fname', or values look like short names."""
    score = 0.0
    if header:
        lowered = header.strip().lower()
        if "first" in lowered and "name" in lowered:
            score = 0.9
        elif lowered.startswith("fname"):
            score = 0.7

    if score == 0.0 and column_values_sample:
        total_length = sum(
            len(str(value).strip()) for value in column_values_sample if value
        )
        non_empty = max(1, sum(1 for value in column_values_sample if value))
        avg_length = total_length / non_empty
        if 2 <= avg_length <= 12:
            score = 0.4

    return {"scores": {_FIELD: round(score, 2)}}


def transform(
    *,
    value: Any,
    **_: Any,
) -> str | None:
    """Strip whitespace and title-case first names."""
    if value in (None, ""):
        return None
    return str(value).strip().title()
