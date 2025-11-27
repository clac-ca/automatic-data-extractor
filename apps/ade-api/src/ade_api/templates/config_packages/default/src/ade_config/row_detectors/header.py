"""
Simple header-row heuristics.

Each `detect_*` function returns a score for the "header" label. The
engine calls all of them for each row and sums the scores.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

# Lowercase words commonly found in column headers
KNOWN_HEADER_WORDS: set[str] = {
    "id", "name", "first", "last", "full", "email", "date", "dept",
    "department", "amount", "total", "qty", "quantity", "price", "status",
    "type", "code", "number", "invoice", "account", "phone", "city", "state",
    "country", "address", "zip", "postal", "notes", "description"
}


def _iter_strings(values: Iterable[Any]) -> list[str]:
    return [
        str(v).strip()
        for v in values
        if isinstance(v, str) and str(v).strip()
    ]


def detect_known_header_words(
    *,
    run: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    row_index: int,
    row_values: list[Any],
    logger: Any | None = None,
    **_: Any,
) -> dict[str, dict[str, float]]:
    """
    Strongest signal: does this row contain known header words?

    Args:
        run: metadata for the current run (IDs, workspace, sheet info)
        state: shared dict persisted across detectors/transforms for caching
        row_index: 1-based stream index for this row
        row_values: raw values from the spreadsheet row
        logger: run-scoped logger for diagnostics
    """
    hits = 0
    for cell in _iter_strings(row_values):
        lowered = cell.lower()
        for word in KNOWN_HEADER_WORDS:
            if word in lowered:
                hits += 1
                break

    if hits >= 2:
        score = 0.60
    elif hits == 1:
        score = 0.35
    else:
        score = 0.0

    return {"scores": {"header": score}}


def detect_mostly_text(
    *,
    run: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    row_index: int,
    row_values: list[Any],
    logger: Any | None = None,
    **_: Any,
) -> dict[str, dict[str, float]]:
    """
    Medium signal: header rows are usually text-heavy.

    Args:
        run: metadata for the current run (IDs, workspace, sheet info)
        state: shared dict persisted across detectors/transforms for caching
        row_index: 1-based stream index for this row
        row_values: raw values from the spreadsheet row
        logger: run-scoped logger for diagnostics
    """
    non_blank = [v for v in row_values if v not in (None, "")]
    if not non_blank:
        return {"scores": {"header": 0.0}}

    string_count = sum(isinstance(v, str) for v in non_blank)
    ratio = string_count / len(non_blank)

    if ratio >= 0.75:
        score = 0.40
    elif ratio >= 0.55:
        score = 0.20
    else:
        score = 0.0

    return {"scores": {"header": score}}


def detect_early_row_bias(
    *,
    run: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    row_index: int,
    row_values: list[Any],
    logger: Any | None = None,
    **_: Any,
) -> dict[str, dict[str, float]]:
    """
    Small nudge: earlier rows are more likely to be headers.

    Args:
        run: metadata for the current run (IDs, workspace, sheet info)
        state: shared dict persisted across detectors/transforms for caching
        row_index: 1-based stream index for this row
        row_values: raw values from the spreadsheet row
        logger: run-scoped logger for diagnostics
    """
    if row_index <= 2:
        score = 0.20
    elif row_index <= 6:
        score = 0.10
    else:
        score = 0.0
    return {"scores": {"header": score}}
