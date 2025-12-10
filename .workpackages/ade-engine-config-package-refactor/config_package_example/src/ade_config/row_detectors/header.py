from __future__ import annotations

from typing import Any

import re

from ade_engine.registry import RowDetectorContext, RowKind, row_detector


COMMON_HEADER_TOKENS = {
    # identity
    "name", "first", "last", "middle", "email", "phone",
    # address
    "address", "street", "city", "state", "province", "postal", "zip",
    # payroll-ish
    "hours", "wages", "gross", "net", "rate", "dues", "pension",
    # employment
    "job", "classification", "status", "start", "end",
}


@row_detector(row_kind=RowKind.HEADER)
def detect_header_row_by_known_words(ctx: RowDetectorContext) -> dict[str, float]:
    """Vote for a row being a header row.

    Heuristic:
      - header rows contain lots of short text labels
      - header rows often include common schema words (email, name, hours, etc.)
    """
    values = ctx.row_values or []
    if not values:
        return {"header": 0.0}

    strings = [v for v in values if isinstance(v, str) and v.strip()]
    if not strings:
        return {"header": 0.0, "data": 0.2}

    # Tokenize across all string cells in the row.
    tokens: set[str] = set()
    for s in strings:
        normalized = re.sub(r"[^a-z0-9]+", " ", s.lower())
        tokens |= {tok for tok in normalized.split() if tok}

    hits = len(tokens & COMMON_HEADER_TOKENS)
    text_ratio = len(strings) / max(len(values), 1)

    # Simple score: header-like if it has both "words we expect" and lots of text cells.
    score = min(1.0, (hits / 4) * 0.6 + text_ratio * 0.4)

    # Reduce data likelihood a bit (helps the classifier separate)
    return {"header": score, "data": -score * 0.3}
