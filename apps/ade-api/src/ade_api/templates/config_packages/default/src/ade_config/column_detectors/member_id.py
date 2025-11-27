"""Detect and normalize unique member identifiers."""

from __future__ import annotations

from typing import Any

_FIELD = "member_id"


def detect_member_id(
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
    Return a confidence score for the member ID column.

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
    header_score = 0.0
    if header:
        lowered = header.strip().lower()
        if "member" in lowered and "id" in lowered:
            header_score = 0.9
        elif lowered in {"id", "member #", "member no", "member number"}:
            header_score = 0.7
        elif "id" in lowered:
            header_score = 0.5

    numeric_hits = sum(
        1 for value in sample_values
        if value is not None and str(value).strip().isdigit()
    )
    sample_score = (numeric_hits / max(1, len(sample_values))) * 0.3
    score = round(min(1.0, header_score + sample_score), 2)

    return score


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
    Normalize identifiers to trimmed uppercase strings.

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
    cleaned = str(value).strip()
    normalized = cleaned.upper() if cleaned else None
    return {field_name: normalized}


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
    Return validation issues for missing identifiers.

    Args:
        run: metadata identifying the run, workspace, config, and sheet.
        state: mutable cache shared across detectors/transforms for this run.
        row_index: 1-based row number (for issue context).
        field_name: canonical field being validated.
        value: canonical value after any transforms.
        row: canonical row dict for cross-field checks.
        field_meta: manifest metadata for this field (required/allowed/etc).
        manifest/env: manifest/env knobs for extra context (allowed lists, etc.).
        logger: run-scoped logger for emitting validation notes.
    """
    issues: list[dict[str, Any]] = []
    required = bool(field_meta and field_meta.get("required"))

    if value in (None, "") and required:
        issues.append(
            {
                "code": "missing_required",
                "severity": "error",
                "message": f"{field_name.replace('_', ' ').title()} is required."
            }
        )

    return issues
