"""
Simple, strong header heuristics.

We return tiny score deltas; the engine sums them.
Add new rules by defining more `detect_*` functions with the same signature.

Signals we use:
  1) KNOWN HEADER WORDS (strong): if a row contains common column names (id, name, email, date, etc.)
  2) MOSTLY TEXT (medium): headers are usually mostly short text values
  3) EARLY ROW (small): headers tend to be near the top
"""

from __future__ import annotations

# Lowercase words commonly found in column headers
KNOWN_HEADER_WORDS = {
    "id","name","first","last","full","email","date","dept","department",
    "amount","total","qty","quantity","price","status","type","code","number",
    "invoice","account","phone","city","state","country","address","zip","postal",
    "notes","description"
}

def detect_known_header_words(
    *,
    job, state, row_index: int, row_values: list, logger=None, **_
) -> dict:
    """
    Strongest single: does this row contain known column header words?
    """
    hits = 0
    for v in row_values:
        if isinstance(v, str):
            s = v.strip().lower()
            if not s:
                continue
            for w in KNOWN_HEADER_WORDS:
                if w in s:
                    hits += 1
                    break

    # 2+ hits → strong boost, 1 hit → moderate boost
    if hits >= 2:
        score = 0.60
    elif hits == 1:
        score = 0.35
    else:
        score = 0.0
    return {"scores": {"header": score}}


def detect_mostly_text(
    *,
    job, state, row_index: int, row_values: list, logger=None, **_
) -> dict:
    """
    Medium signal: headers are usually text-heavy.
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
    job, state, row_index: int, row_values: list, logger=None, **_
) -> dict:
    """
    Small nudge: earlier rows are more likely to be headers.
    """
    if row_index <= 2:
        score = 0.20
    elif row_index <= 6:
        score = 0.10
    else:
        score = 0.0
    return {"scores": {"header": score}}