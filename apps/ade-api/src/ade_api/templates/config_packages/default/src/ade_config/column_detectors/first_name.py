"""Detect simple first-name columns and normalize casing."""

from __future__ import annotations

from typing import Any

_FIELD = "first_name"


def detect_first_name(
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
    Heuristic: header mentions 'first name' or 'fname', or values look like short names.

    Args:
        run/state: run metadata and shared cache available for scoring.
        field_name: canonical field this detector serves.
        field_meta: manifest metadata describing synonyms/requirements.
        header: cleaned header text for this column (if present).
        column_values_sample: stratified sample of column values.
        column_values: full column (only touch if necessary).
        table/column_index: full table context and column position.
        manifest/env: manifest/env overrides for extra hints.
        logger: logger for diagnostics.
        **_: extra future-proof keywords.
    """
    sample_values = column_values_sample or []
    score = 0.0
    if header:
        lowered = header.strip().lower()
        if "first" in lowered and "name" in lowered:
            score = 0.9
        elif lowered.startswith("fname"):
            score = 0.7

    if score == 0.0 and sample_values:
        total_length = sum(
            len(str(value).strip()) for value in sample_values if value
        )
        non_empty = max(1, sum(1 for value in sample_values if value))
        avg_length = total_length / non_empty
        if 2 <= avg_length <= 12:
            score = 0.4

    return round(score, 2)


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
    Strip whitespace and title-case first names.

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
