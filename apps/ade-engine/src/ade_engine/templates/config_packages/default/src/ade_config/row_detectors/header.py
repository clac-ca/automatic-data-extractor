from __future__ import annotations

import re

from ade_engine.registry.models import RowKind


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


def register(registry):
    registry.register_row_detector(detect_header_row_by_known_words, row_kind=RowKind.HEADER.value, priority=0)


def detect_header_row_by_known_words(
    *,
    row_index,
    row_values,
    sheet_name,
    metadata,
    state,
    input_file_name,
    logger,
) -> dict[str, float] | None:
    """Vote for a row being a header row.

    Heuristic:
      - header rows contain lots of short text labels
      - header rows often include common schema words (email, name, hours, etc.)
    """
    values = row_values or []
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
