"""Heuristics for identifying simple member ID columns."""

from __future__ import annotations

from typing import Any

SYNONYMS = {"member id", "memberid", "member#", "member number"}


def detect_member_id_from_header(
    *,
    header: str | None = None,
    logger: Any | None = None,
    event_emitter: Any | None = None,
    **_: Any,
) -> float | dict[str, float]:
    """Score headers that look like member identifiers."""

    if not header:
        return 0.0

    normalized = header.strip().lower().replace("_", " ").replace("-", " ")
    compact = normalized.replace(" ", "")

    if compact in SYNONYMS or normalized in SYNONYMS:
        if logger:
            logger.debug("Header member_id match: %r", header)
        return 1.0

    if "member" in compact and "id" in compact:
        return 0.6

    return 0.0


def detect_member_id_from_values(
    *,
    column_values_sample: list[Any] | None = None,
    logger: Any | None = None,
    event_emitter: Any | None = None,
    **_: Any,
) -> float | dict[str, float]:
    """Lightweight detector for mostly-numeric identifiers."""

    if not column_values_sample:
        return 0.0

    observed = 0
    numeric_like = 0
    for value in column_values_sample:
        if value in (None, ""):
            continue
        observed += 1
        text = str(value).strip()
        if text.isdigit():
            numeric_like += 1

    if observed == 0:
        return 0.0

    ratio = numeric_like / observed
    if ratio >= 0.9:
        return 0.6
    if ratio >= 0.6:
        return 0.35
    return 0.0
