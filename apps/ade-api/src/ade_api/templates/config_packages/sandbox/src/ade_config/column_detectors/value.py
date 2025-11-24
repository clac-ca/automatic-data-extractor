"""Detect a generic value/amount column for sandbox runs."""

from __future__ import annotations

from typing import Any


def detect_value(
    *,
    header: str | None,
    column_values_sample: list[Any],
    **_: Any,
) -> float:
    """Return a confidence score favoring the "value" header name."""
    lowered = (header or "").strip().lower()
    header_score = 0.8 if lowered == "value" else 0.4 if "value" in lowered else 0.0
    non_empty = sum(1 for value in column_values_sample if value not in (None, ""))
    sample_score = min(1.0, non_empty / max(1, len(column_values_sample))) * 0.2
    return round(min(1.0, header_score + sample_score), 2)


def transform(*, value: Any, **_: Any) -> dict[str, Any]:
    """Normalize values to stripped strings for workbook output."""
    if value is None:
        return {"value": None}
    cleaned = str(value).strip()
    return {"value": cleaned or None}
