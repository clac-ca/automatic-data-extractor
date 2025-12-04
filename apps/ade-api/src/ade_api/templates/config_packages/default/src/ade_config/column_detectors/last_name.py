"""
Example: Readable last-name detector using both dict and float scoring styles.

Detectors may return:
    • A float → affects only `last_name`
    • A dict  → can adjust multiple fields (e.g., boost last_name and penalize first_name)

This example mirrors the first-name detector and is useful for showing symmetry
between the two field types.
"""

from __future__ import annotations
from typing import Any

# Small demo list of common surnames.
COMMON_LAST_NAMES = {
    "smith", "johnson", "williams", "brown", "jones", "garcia",
    "miller", "davis", "rodriguez", "martinez", "hernandez",
    "lopez", "gonzalez", "wilson", "anderson",
}

# ---------------------------------------------------------------------------
# HEADER-BASED DETECTOR
# ---------------------------------------------------------------------------

def detect_last_name_from_header(
    *,
    header: str | None,
    logger=None,
    event_emitter=None,
    **_: Any,
) -> dict[str, float]:
    """
    Score headers that look like last-name columns.

    Returns a DICT so we can influence both fields when appropriate:
        {"last_name": 1.0, "first_name": -0.5}

    Heuristics:
      • "last", "surname", "family" → strong last-name match
      • "first", "given" → signal for the *other* detector
      • "name" → ambiguous
    """

    if not header:
        return {"last_name": 0.0, "first_name": 0.0}

    lowered = header.strip().lower()

    # Strong surname keywords
    if any(word in lowered for word in ("last", "surname", "family", "lname")):
        logger and logger.debug("Detected last-name header: %r", header)
        return {"last_name": 1.0, "first_name": -0.5}

    # Opposite signal: likely a first-name column instead
    if any(word in lowered for word in ("first", "given", "fname")):
        return {"last_name": -0.5, "first_name": 1.0}

    # Ambiguous but relevant
    if "name" in lowered:
        return {"last_name": 0.25, "first_name": 0.25}

    return {"last_name": 0.0, "first_name": 0.0}

# ---------------------------------------------------------------------------
# VALUE-BASED DETECTOR
# ---------------------------------------------------------------------------

def detect_last_name_from_values(
    *,
    column_values_sample: list[Any],
    logger=None,
    event_emitter=None,
    **_: Any,
) -> float:
    """
    Detect last names from sample values.

    This detector returns a FLOAT, affecting only `last_name`.

    Heuristics:
      • One-token strings (2–16 chars) → likely surnames
      • Matches in COMMON_LAST_NAMES → strong signal
      • Comma or multiple tokens → likely full names (penalize)
      • Emails → penalized (not name-like)
    """

    if not column_values_sample:
        return 0.0

    clean_surnames = 0
    common_hits = 0
    full_names = 0
    email_like = 0

    for value in column_values_sample:
        if not isinstance(value, str):
            continue

        cleaned = value.strip()
        if not cleaned:
            continue

        # Email addresses are not surnames
        if "@" in cleaned:
            email_like += 1
            continue

        tokens = cleaned.split()

        # Multi-token or comma → likely full name
        if "," in cleaned or len(tokens) >= 2:
            full_names += 1
            continue

        # Single-token strings: potential surnames
        if 2 <= len(cleaned) <= 16:
            clean_surnames += 1
            if cleaned.lower() in COMMON_LAST_NAMES:
                common_hits += 1

    # Strongest match: common last names
    if common_hits >= 2:
        return 1.0

    if clean_surnames >= 3 and full_names == 0:
        return 0.8

    if full_names > clean_surnames:
        return -0.25

    if email_like:
        return -0.3

    if clean_surnames:
        return 0.4

    return 0.0

# ---------------------------------------------------------------------------
# TRANSFORM FUNCTION
# ---------------------------------------------------------------------------

def transform(
    *,
    value: Any,
    logger=None,
    event_emitter=None,
    **_: Any,
) -> dict[str, Any]:
    """
    Normalize last names into title case.

    Transform functions always return a dict keyed by field.
    """

    if value in (None, ""):
        return {"last_name": None}

    return {"last_name": str(value).strip().title() or None}
