"""Lightweight detector for generic numeric value columns."""

from __future__ import annotations

from typing import Any

TOKENS = {"value", "amount", "score", "total"}


def detect_value_from_header(
    *,
    header: str | None = None,
    logger: Any | None = None,
    event_emitter: Any | None = None,
    **_: Any,
) -> float:
    """Bias headers that mention values or amounts."""

    if not header:
        return 0.0

    normalized = header.strip().lower().replace("_", " ").replace("-", " ")
    compact = normalized.replace(" ", "")

    if compact in TOKENS or normalized in TOKENS:
        return 0.9

    if any(token in compact for token in TOKENS):
        return 0.5

    return 0.0


def detect_value_from_values(
    *,
    column_values_sample: list[Any] | None = None,
    logger: Any | None = None,
    event_emitter: Any | None = None,
    **_: Any,
) -> float:
    """Treat mostly-numeric samples as likely value columns."""

    if not column_values_sample:
        return 0.0

    observed = 0
    numeric_like = 0
    for value in column_values_sample:
        if value in (None, ""):
            continue
        observed += 1
        text = str(value).strip().replace(",", "")
        if text.replace(".", "", 1).isdigit():
            numeric_like += 1

    if observed == 0:
        return 0.0

    ratio = numeric_like / observed
    if ratio >= 0.9:
        return 0.7
    if ratio >= 0.6:
        return 0.35
    return 0.0
