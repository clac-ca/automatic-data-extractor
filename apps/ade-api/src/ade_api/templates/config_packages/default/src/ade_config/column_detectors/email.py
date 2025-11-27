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
    field_name: str = _FIELD,
    field_meta: dict[str, Any] | None = None,
    header: str | None = None,
    column_values_sample: list[Any] | None = None,
    column_values: tuple[Any, ...] | None = None,
    table: dict[str, Any] | None = None,
    column_index: int | None = None,
    manifest: dict[str, Any] | None = None,
    env: dict[str, Any] | None = None,
    logger: Any | None = None,
    **_: Any,
) -> float:
    """
    Heuristic: header looks like email and/or most sample values look like email addresses.

    Args:
        run: metadata identifying the run, workspace, config, and sheet.
        state: mutable cache shared across detectors/transforms for this run.
        field_name: canonical name this detector evaluates (prefilled for convenience).
        field_meta: manifest metadata describing synonyms, hints, and requirements.
        header: cleaned header cell text for this column (or None when blank).
        column_values_sample: stratified slice of the column (head/mid/tail).
        column_values: full column values (already materialized when needed).
        table: the materialized table ({'headers': [...], 'rows': [[...], ...]}).
        column_index: 1-based index for this column in the table.
        manifest/env: manifest and config env overrides (helpers can read settings).
        logger: run-scoped logger for emitting notes.
        **_: future-proof keyword arguments (ignore what you do not need).
    """
    sample_values = column_values_sample or []
    score = 0.0

    if header:
        lowered = header.strip().lower()
        if "email" in lowered:
            score = 0.85

    if sample_values:
        matches = sum(
            1
            for value in sample_values
            if value and _EMAIL_RE.match(str(value).strip())
        )
        if matches:
            score = max(score, matches / max(1, len(sample_values)))

    return round(min(score, 1.0), 2)


def transform(
    *,
    run: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    row_index: int | None = None,
    field_name: str = _FIELD,
    value: Any = None,
    row: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    env: dict[str, Any] | None = None,
    logger: Any | None = None,
    **_: Any,
) -> dict[str, Any] | None:
    """
    Normalize email addresses to lower-case strings, or None.

    Args:
        run: metadata identifying the run, workspace, config, and sheet.
        state: mutable cache shared across detectors/transforms for this run.
        row_index: 1-based row number (useful for logging/issues).
        field_name: canonical field being transformed.
        value: raw mapped value before normalization.
        row: dictionary of canonical fields for the current row.
        manifest/env: manifest/env knobs for context-aware transforms.
        logger: run-scoped logger for emitting notes.
    """
    if value in (None, ""):
        return {field_name: None}
    return {field_name: str(value).strip().lower()}


def validate(
    *,
    run: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    row_index: int | None = None,
    field_name: str = _FIELD,
    value: Any = None,
    row: dict[str, Any] | None = None,
    field_meta: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    env: dict[str, Any] | None = None,
    logger: Any | None = None,
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
