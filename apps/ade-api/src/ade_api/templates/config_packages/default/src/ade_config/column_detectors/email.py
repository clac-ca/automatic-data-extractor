"""Detect email columns and normalize / validate email addresses."""

from __future__ import annotations

import re
from typing import Any

_FIELD = "email"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.IGNORECASE)


def detect_email(
    *,
    header: str | None,
    column_values_sample: list[Any],
    **_: Any,
) -> dict[str, dict[str, float]]:
    """
    Heuristic: header looks like email and/or most sample values look
    like email addresses.
    """
    score = 0.0

    if header:
        lowered = header.strip().lower()
        if "email" in lowered:
            score = 0.85

    if column_values_sample:
        matches = sum(
            1
            for value in column_values_sample
            if value and _EMAIL_RE.match(str(value).strip())
        )
        if matches:
            score = max(score, matches / max(1, len(column_values_sample)))

    return {"scores": {_FIELD: round(min(score, 1.0), 2)}}


def transform(
    *,
    value: Any,
    **_: Any,
) -> str | None:
    """Normalize email addresses to lower-case strings, or None."""
    if value in (None, ""):
        return None
    return str(value).strip().lower()


def validate(
    *,
    value: Any,
    field_name: str = _FIELD,
    field_meta: dict[str, Any] | None = None,
    **_: Any,
) -> list[dict[str, Any]]:
    """
    Return issue dicts for missing or invalid email values.

    The engine will add row index and field name; we only supply
    code / severity / message (and optional details).
    """
    issues: list[dict[str, Any]] = []

    required = bool(field_meta and field_meta.get("required"))

    if value in (None, ""):
        if required:
            issues.append(
                {
                    "code": "missing_required",
                    "severity": "error",
                    "message": f"{field_name.replace('_', ' ').title()} is required."
                }
            )
        return issues

    if not _EMAIL_RE.match(str(value).strip()):
        issues.append(
            {
                "code": "invalid_format",
                "severity": "error",
                "message": "Email must look like user@example.com."
            }
        )

    return issues
