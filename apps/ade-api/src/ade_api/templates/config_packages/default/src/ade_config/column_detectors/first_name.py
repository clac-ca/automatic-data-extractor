"""
Example: Readable first-name detector showing BOTH return styles.

Detectors may return:
    • A float → applies only to the field being detected (e.g., 0.8 for first_name)
    • A dict → lets you influence multiple fields (e.g., {"first_name": 1.0, "last_name": -0.5})

This example demonstrates both patterns.
"""

from __future__ import annotations
from typing import Any

# A small demo list of common first names. Real detectors often use much larger sets.
COMMON_FIRST_NAMES = {
    "james", "mary", "john", "patricia", "robert", "jennifer",
    "michael", "linda", "william", "elizabeth", "david", "barbara",
    "richard", "susan", "joseph", "karen",
}

# ---------------------------------------------------------------------------
# HEADER-BASED DETECTOR
# ---------------------------------------------------------------------------

def detect_first_name_from_header(
    *,
    header: str | None,
    logger=None,
    event_emitter=None,
    **_: Any,
) -> dict[str, float]:
    """
    Score headers that look like first-name columns.

    This detector returns a DICT so it can boost first_name *and* optionally
    penalize last_name (or vice-versa). This is useful when one header
    definition implies the other.
    """

    if not header:
        return {"first_name": 0.0, "last_name": 0.0}

    lowered = header.strip().lower()

    # Strong indicators of first name
    if any(word in lowered for word in ("first", "given", "fname")):
        logger and logger.debug("Detected first-name header: %r", header)
        return {"first_name": 1.0, "last_name": -0.5}

    # Strong indicators of last name — push that field up instead
    if any(word in lowered for word in ("last", "surname", "family", "lname")):
        return {"first_name": -0.5, "last_name": 1.0}

    # Generic "name" columns: treat as ambiguous
    if "name" in lowered:
        return {"first_name": 0.25, "last_name": 0.25}

    return {"first_name": 0.0, "last_name": 0.0}

# ---------------------------------------------------------------------------
# VALUE-BASED DETECTOR
# ---------------------------------------------------------------------------

def detect_first_name_from_values(
    *,
    column_values_sample: list[Any],
    logger=None,
    event_emitter=None,
    **_: Any,
) -> float:
    """
    Score column values that *look* like first names.

    This detector returns a FLOAT, affecting only 'first_name'.

    Heuristics demonstrated:
      • Simple one-token strings → likely first names
      • Matching common first names → strong signal
      • Values with comma or multi-word names → penalized (likely full names)
    """

    if not column_values_sample:
        return 0.0

    simple_firsts = 0
    common_hits = 0
    full_names = 0

    for value in column_values_sample:
        if not isinstance(value, str):
            continue

        cleaned = value.strip()
        if not cleaned or "@" in cleaned:  # ignore empty and emails
            continue

        # “Last, First” or multi-token → treat as full names
        if "," in cleaned:
            full_names += 1
            continue

        tokens = cleaned.split()

        # One-word candidates → likely first names
        if len(tokens) == 1 and 2 <= len(tokens[0]) <= 14:
            simple_firsts += 1
            if tokens[0].lower() in COMMON_FIRST_NAMES:
                common_hits += 1

        # More than one token → full name
        elif len(tokens) >= 2:
            full_names += 1

    # Strongest signals
    if common_hits >= 3:
        return 1.0

    if simple_firsts >= 3 and simple_firsts > full_names:
        return 0.75

    # Column looks more like full names
    if full_names > simple_firsts:
        return -0.3

    # At least some plausible first names
    if simple_firsts:
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
    Example transform: standardize first names.

    Return format must always be a dict keyed by the field.
    """

    if value in (None, ""):
        return {"first_name": None}

    return {"first_name": str(value).strip().title() or None}