"""Detect simple last-name columns and normalize casing."""

from __future__ import annotations

from typing import Any

_FIELD = "last_name"


def detect_last_name(
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
    """
    Heuristic: header mentions 'last name'/'surname' or values look like surnames.

    Args:
        run/state: run metadata and shared cache available for scoring.
        header: cleaned header text for this column (if present).
        column_values_sample: stratified sample of column values.
        column_index: full table context and column position.
        logger/event_emitter: logger for diagnostics; event_emitter for structured run events.
        **_: extra future-proof keywords.
    """
    sample_values = column_values_sample or []
    score = 0.0
    if header:
        lowered = header.strip().lower()
        if "last" in lowered and "name" in lowered:
            score = 0.9
        elif lowered in {"surname", "family name"}:
            score = 0.8

    if score == 0.0 and sample_values:
        total_length = sum(
            len(str(value).strip()) for value in sample_values if value
        )
        non_empty = max(1, sum(1 for value in sample_values if value))
        avg_length = total_length / non_empty
        if 2 <= avg_length <= 16:
            score = 0.35

    return round(score, 2)


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
    """
    Strip whitespace and title-case last names.

    Args:
        run/state: run metadata and shared cache available during transforms.
        row_index: 1-based row index for diagnostics.
        field_name: canonical field being updated.
        value: raw canonical value before normalization.
        row: full canonical row dict for cross-field work.
        manifest/env: manifest/env overrides if you need extra hints.
        logger: logger for diagnostics.
    """
    if value in (None, ""):
        return {field_name: None}
    return {field_name: str(value).strip().title()}
