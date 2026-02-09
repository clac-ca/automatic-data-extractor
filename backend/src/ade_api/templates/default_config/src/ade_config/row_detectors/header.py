"""ADE row detector template: `header`

Row detectors vote on what each row represents (header vs data vs unknown). ADE
uses these votes to pick header rows and detect table regions.

Return value
------------
- Return a score patch (`dict[str, float]`) or `None`.
- Keys are row kinds like `"header"` and `"data"` (scores are additive across detectors).
- Higher total score wins the per-row classification.

Template goals
--------------
- Keep the default heuristic fast (no large scans; operate on the current row only).
- Be deterministic and reasonably conservative (avoid overfitting to one dataset).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, MutableMapping, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ade_engine.extensions.registry import Registry
    from ade_engine.infrastructure.observability.logger import RunLogger
    from ade_engine.infrastructure.settings import Settings


def register(registry: Registry) -> None:
    """Register this config package's header row detector(s)."""
    registry.register_row_detector(detect_header_row_by_known_words, row_kind="header", priority=0)


def detect_header_row_by_known_words(
    *,
    row_index: int,  # 1-based row number in the scanned sheet (Excel-style)
    row_values: Sequence[Any],  # Raw cell values for this row (may include None/""/numbers)
    sheet_name: str,  # Worksheet title
    settings: Settings,  # Engine Settings
    metadata: Mapping[str, Any],  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: MutableMapping[str, Any],  # Mutable dict shared across the run
    input_file_name: str,  # Input filename (basename)
    logger: RunLogger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Vote for a row being a header row.

    Heuristic:
      - header rows contain lots of short text labels
      - header rows often include common schema words (email, name, hours, etc.)

    Scoring:
      - Returns a positive `header` score.
      - Also returns a small negative `data` score to help separation (optional pattern).
    """
    common_header_tokens = {
        # identity
        "name",
        "first",
        "last",
        "middle",
        "email",
        "phone",
        # address
        "address",
        "street",
        "city",
        "state",
        "province",
        "postal",
        "zip",
        # payroll-ish
        "hours",
        "wages",
        "gross",
        "net",
        "rate",
        "dues",
        "pension",
        # employment
        "job",
        "classification",
        "status",
        "start",
        "end",
    }

    values = row_values or []
    if not values:
        return {"header": 0.0}

    strings = [v for v in values if isinstance(v, str) and v.strip()]
    if not strings:
        return {"header": 0.0, "data": 0.2}

    # Tokenize across all string cells in the row.
    tokens: set[str] = set()
    for s in strings:
        # Avoid treating email addresses as "header-like" just because they
        # happen to contain words like "email" (e.g. foo@email.com).
        if "@" in s:
            continue
        normalized = re.sub(r"[^a-z0-9]+", " ", s.lower())
        tokens |= {tok for tok in normalized.split() if tok}

    hits = len(tokens & common_header_tokens)
    text_ratio = len(strings) / max(len(values), 1)

    # Simple score: header-like if it has both "words we expect" and lots of text cells.
    score = min(1.0, (hits / 4) * 0.6 + text_ratio * 0.4)

    # Reduce data likelihood a bit (helps the classifier separate)
    return {"header": score, "data": -score * 0.3}
