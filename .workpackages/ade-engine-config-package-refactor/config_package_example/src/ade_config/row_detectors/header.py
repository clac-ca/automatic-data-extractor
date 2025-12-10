from __future__ import annotations

from typing import Any

from ade_engine.registry import row_detector
from ade_config.helpers import header_tokens


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


@row_detector
def detect_header_row_by_known_words(*, ctx: Any, **_: Any) -> dict[str, float]:
    """Vote for a row being a header row.

    Heuristic:
      - header rows contain lots of short text labels
      - header rows often include common schema words (email, name, hours, etc.)
    """
    values = getattr(ctx, "row_values", None) or []
    if not values:
        return {"header": 0.0}

    strings = [v for v in values if isinstance(v, str) and v.strip()]
    if not strings:
        return {"header": 0.0, "data": 0.2}

    # Tokenize across all string cells in the row.
    tokens: set[str] = set()
    for s in strings:
        tokens |= header_tokens(s)

    hits = len(tokens & COMMON_HEADER_TOKENS)
    text_ratio = len(strings) / max(len(values), 1)

    # Simple score: header-like if it has both "words we expect" and lots of text cells.
    score = min(1.0, (hits / 4) * 0.6 + text_ratio * 0.4)

    # Reduce data likelihood a bit (helps the classifier separate)
    return {"header": score, "data": -score * 0.3}
