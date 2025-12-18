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


# -----------------------------------------------------------------------------
# Shared state namespacing
# -----------------------------------------------------------------------------
# `state` is a mutable dict shared across the run.
# Best practice: store everything your config package needs under ONE top-level key.
#
# IMPORTANT: Keep this constant the same across your hooks/detectors/transforms so
# they can share cached values and facts.
STATE_NAMESPACE = "ade.config_package_template"
STATE_SCHEMA_VERSION = 1


COMMON_HEADER_TOKENS = {
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


def register(registry) -> None:
    """Register this config package's header row detector(s)."""
    registry.register_row_detector(detect_header_row_by_known_words, row_kind="header", priority=0)


def detect_header_row_by_known_words(
    *,
    row_index: int,  # 1-based row number in the scanned sheet (Excel-style)
    row_values: list[object],  # Raw cell values for this row (may include None/""/numbers)
    sheet_name: str,  # Worksheet title
    settings,  # Engine Settings
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    input_file_name: str,  # Input filename (basename)
    logger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Vote for a row being a header row.

    Heuristic:
      - header rows contain lots of short text labels
      - header rows often include common schema words (email, name, hours, etc.)

    Scoring:
      - Returns a positive `header` score.
      - Also returns a small negative `data` score to help separation (optional pattern).
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
        # Avoid treating email addresses as "header-like" just because they
        # happen to contain words like "email" (e.g. foo@email.com).
        if "@" in s:
            continue
        normalized = re.sub(r"[^a-z0-9]+", " ", s.lower())
        tokens |= {tok for tok in normalized.split() if tok}

    hits = len(tokens & COMMON_HEADER_TOKENS)
    text_ratio = len(strings) / max(len(values), 1)

    # Simple score: header-like if it has both "words we expect" and lots of text cells.
    score = min(1.0, (hits / 4) * 0.6 + text_ratio * 0.4)

    # Reduce data likelihood a bit (helps the classifier separate)
    return {"header": score, "data": -score * 0.3}
