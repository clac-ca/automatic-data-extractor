"""Detect email columns and normalize / validate email addresses."""

from __future__ import annotations

import re
from typing import Any

_FIELD = "email"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.IGNORECASE)


def detect_email(
    *,
    run: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    raw_table: Any | None = None,
    column_index: int,
    header: str | None,
    column_values_sample: list[Any],
    column_values: list[Any],
    manifest: dict[str, Any] | None = None,
    logger,
    event_emitter,
    **_: Any,
) -> float:
    """Detector: combine header and sample-value checks."""

    sample_values = column_values_sample or []
    score = 0.0

    if header:
        lowered = header.strip().lower()
        if "email" in lowered:
            score = 0.85
        if "e-mail" in lowered:
            event_emitter.custom(
                "detector.nonstandard_header",
                field=_FIELD,
                header=header,
                note="Header uses 'e-mail' spelling",
            )

    if sample_values:
        matches = sum(1 for value in sample_values if value and _EMAIL_RE.match(str(value).strip()))
        if matches:
            score = max(score, matches / max(1, len(sample_values)))

    logger.debug("email header=%r score=%.2f column=%s", header, score, column_index)
    return round(min(score, 1.0), 2)


def transform(
    *,
    run: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    row_index: int,
    field_name: str,
    value: Any,
    row: dict[str, Any],
    field_config: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    logger,
    event_emitter,
    **_: Any,
) -> dict[str, Any] | None:
    """Normalize email addresses to lower-case strings, or None."""

    if value in (None, ""):
        return {field_name: None}
    return {field_name: str(value).strip().lower()}


def validate(
    *,
    run: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    row_index: int,
    field_name: str,
    value: Any,
    row: dict[str, Any],
    field_config: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    logger,
    event_emitter,
    **_: Any,
) -> list[dict[str, Any]]:
    """Return issue dicts for missing or invalid email values."""

    issues: list[dict[str, Any]] = []

    required = bool(field_config and field_config.get("required"))

    if value in (None, ""):
        if required:
            issues.append(
                {
                    "code": "missing_required",
                    "severity": "error",
                    "message": f"{field_name.replace('_', ' ').title()} is required.",
                }
            )
        return issues

    if not _EMAIL_RE.match(str(value).strip()):
        issues.append(
            {
                "code": "invalid_format",
                "severity": "error",
                "message": "Email must look like user@example.com.",
            }
        )

    return issues
