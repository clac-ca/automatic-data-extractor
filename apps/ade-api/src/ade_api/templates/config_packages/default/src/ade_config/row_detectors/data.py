"""
Simple, general-purpose data-row heuristics.

Each `detect_*` function returns a score for the "data" label. The engine
sums scores across detectors to decide which rows are data.
"""

from __future__ import annotations

import re
from typing import Any

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
PHONE_RE = re.compile(r"^\s*(\+?\d[\d\-\s().]{7,}\d)\s*$")  # loose NA/E.164-ish
AGG_WORDS = {"total", "subtotal", "grand total", "summary", "average", "avg"}


def detect_mixed_text_and_numbers(
    *,
    run: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    row_index: int,
    row_values: list[Any],
    logger: Any | None = None,
    **_: Any,
) -> dict[str, dict[str, float]]:
    """
    Data rows often contain both text and numbers.

    Args:
        run: metadata for the current run (IDs, workspace, sheet info)
        state: shared dict persisted across detectors/transforms for caching
        row_index: 1-based stream index for this row
        row_values: raw values from the spreadsheet row
        logger: run-scoped logger for diagnostics
    """
    non_blank = [v for v in row_values if v not in (None, "")]
    if not non_blank:
        return {"scores": {"data": 0.0}}

    def looks_number_like(x: Any) -> bool:
        if isinstance(x, (int, float)):
            return True
        if isinstance(x, str):
            s = x.strip()
            if not s:
                return False
            s = s.replace(",", "").replace("$", "").replace("£", "").replace("€", "")
            if s.startswith("(") and s.endswith(")"):
                s = "-" + s[1:-1]
            s = s.replace(".", "", 1).lstrip("-")
            return s.isdigit()
        return False

    has_text = any(isinstance(v, str) for v in non_blank)
    has_number = any(looks_number_like(v) for v in non_blank)

    if has_text and has_number:
        score = 0.40
    elif has_number:
        score = 0.20
    elif has_text:
        score = 0.10
    else:
        score = 0.0

    return {"scores": {"data": score}}


def detect_value_patterns(
    *,
    run: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    row_index: int,
    row_values: list[Any],
    logger: Any | None = None,
    **_: Any,
) -> dict[str, dict[str, float]]:
    """
    Look for concrete value shapes common in data rows:
      - email addresses
      - phone numbers
      - valid 9-digit SIN (Luhn)

    Args:
        run: metadata for the current run (IDs, workspace, sheet info)
        state: shared dict persisted across detectors/transforms for caching
        row_index: 1-based stream index for this row
        row_values: raw values from the spreadsheet row
        logger: run-scoped logger for diagnostics
    """
    non_blank = [v for v in row_values if v not in (None, "")]
    if not non_blank:
        return {"scores": {"data": 0.0}}

    has_email = any(isinstance(v, str) and EMAIL_RE.match(v.strip()) for v in non_blank)
    has_phone = any(isinstance(v, str) and PHONE_RE.match(v) for v in non_blank)

    def looks_valid_sin(x: Any) -> bool:
        s = "".join(ch for ch in str(x) if ch.isdigit())
        if len(s) != 9 or len(set(s)) == 1:
            return False
        total = 0
        for i, ch in enumerate(reversed(s), start=1):
            d = int(ch)
            if i % 2 == 0:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0

    has_sin = any(looks_valid_sin(v) for v in non_blank)

    hits = sum([has_email, has_phone, has_sin])
    if hits == 0:
        score = 0.0
    elif hits == 1:
        score = 0.35
    elif hits == 2:
        score = 0.45
    else:
        score = 0.55

    return {"scores": {"data": score}}
