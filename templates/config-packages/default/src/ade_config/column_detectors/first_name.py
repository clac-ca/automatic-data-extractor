"""Detect simple first-name columns."""

from __future__ import annotations

from typing import Any

_FIELD = "first_name"


def detect(*, header: str | None, column_values_sample: list[Any], **_: Any) -> dict[str, dict[str, float]]:
    score = 0.0
    if header:
        lowered = header.lower()
        if "first" in lowered and "name" in lowered:
            score = 0.9
        elif lowered.startswith("fname"):
            score = 0.7
    if score == 0.0 and column_values_sample:
        avg_length = sum(len(str(value).strip()) for value in column_values_sample if value) / max(
            1, sum(1 for value in column_values_sample if value)
        )
        if 2 <= avg_length <= 12:
            score = 0.4
    return {"scores": {_FIELD: round(score, 2)}}


def transform(value: Any, /) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip().title()
