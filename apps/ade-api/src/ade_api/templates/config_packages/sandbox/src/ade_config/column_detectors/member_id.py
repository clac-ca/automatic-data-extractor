"""Detect a member identifier column for sandbox runs."""

from __future__ import annotations

from typing import Any


def detect_member_id(
    *,
    header: str | None,
    column_values_sample: list[Any],
    **_: Any,
) -> float:
    """Return a confidence score based on header match and numeric samples."""
    header_score = 1.0 if (header or "").strip().lower() in {"member_id", "member id"} else 0.0
    numeric_hits = sum(
        1 for value in column_values_sample if value is not None and str(value).strip().isdigit()
    )
    sample_score = min(1.0, numeric_hits / max(1, len(column_values_sample))) * 0.3
    return round(min(1.0, header_score + sample_score), 2)


def transform(*, value: Any, **_: Any) -> dict[str, Any]:
    """Normalize identifiers to trimmed uppercase strings."""
    if value in (None, ""):
        return {"member_id": None}
    cleaned = str(value).strip()
    return {"member_id": cleaned.upper() or None}
