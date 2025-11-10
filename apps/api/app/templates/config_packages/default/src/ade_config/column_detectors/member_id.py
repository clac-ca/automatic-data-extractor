"""Detect and normalize unique member identifiers."""

from __future__ import annotations

from typing import Any

_FIELD = "member_id"


def detect(*, header: str | None, column_values_sample: list[Any], **_: Any) -> dict[str, dict[str, float]]:
    """Return a confidence score for the member identifier column."""

    header_score = 0.7 if header and "id" in header.lower() else 0.0
    numeric_hits = sum(1 for value in column_values_sample if str(value).strip().isdigit())
    sample_score = numeric_hits / max(1, len(column_values_sample)) * 0.3
    score = round(min(1.0, header_score + sample_score), 2)
    return {"scores": {_FIELD: score}}


def transform(value: Any, /) -> str | None:
    """Normalise identifiers to trimmed uppercase strings."""

    if value in (None, ""):
        return None
    cleaned = str(value).strip()
    return cleaned.upper() if cleaned else None


def validate(value: Any, /) -> list[str]:
    """Return validation issues for missing identifiers."""

    if value in (None, ""):
        return ["member_id is required"]
    return []
