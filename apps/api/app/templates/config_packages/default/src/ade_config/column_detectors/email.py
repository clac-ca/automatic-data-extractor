"""Detect email columns and validate addresses."""

from __future__ import annotations

import re
from typing import Any

_FIELD = "email"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.IGNORECASE)


def detect(
    *,
    header: str | None,
    column_values_sample: list[Any],
    **_: Any,
) -> dict[str, dict[str, float]]:
    score = 0.0
    if header and "email" in header.lower():
        score = 0.85
    if column_values_sample:
        matches = sum(
            1
            for value in column_values_sample
            if value and _EMAIL_RE.match(str(value).strip())
        )
        score = max(score, matches / max(1, len(column_values_sample)))
    return {"scores": {_FIELD: round(min(score, 1.0), 2)}}


def transform(value: Any, /) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip().lower()


def validate(value: Any, /) -> list[str]:
    if value in (None, ""):
        return []
    if not _EMAIL_RE.match(str(value)):
        return ["invalid email address"]
    return []
