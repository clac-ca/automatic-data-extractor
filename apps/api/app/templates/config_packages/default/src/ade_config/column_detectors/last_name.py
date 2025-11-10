"""Detect simple last-name columns."""

from __future__ import annotations

from typing import Any

_FIELD = "last_name"


def detect(*, header: str | None, column_values_sample: list[Any], **_: Any) -> dict[str, dict[str, float]]:
    score = 0.0
    if header:
        lowered = header.lower()
        if "last" in lowered and "name" in lowered:
            score = 0.9
        elif lowered in {"surname", "family name"}:
            score = 0.8
    if score == 0.0 and column_values_sample:
        avg_length = sum(len(str(value).strip()) for value in column_values_sample if value) / max(
            1, sum(1 for value in column_values_sample if value)
        )
        if 2 <= avg_length <= 16:
            score = 0.35
    return {"scores": {_FIELD: round(score, 2)}}


def transform(value: Any, /) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip().title()
