"""
Last-name detector and transform.

This mirrors the style and teaching approach of the first-name detector:
    • Full real-world signatures
    • No helpers or abstractions
    • Inline logic so users can learn and extend easily
    • Returns float (value-based) or dict (header-based)
"""

from __future__ import annotations

from typing import Any

COMMON_LAST_NAMES = {
    # Small sample set; real-world detectors will use larger dictionaries
    "smith", "johnson", "williams", "brown", "jones", "garcia",
    "miller", "davis", "rodriguez", "martinez", "hernandez",
    "lopez", "gonzalez", "wilson", "anderson", "thomas", "taylor",
}

# ---------------------------------------------------------------------------
# HEADER-BASED DETECTOR
# ---------------------------------------------------------------------------

def detect_last_name_from_header(
    *,
    run: Any | None = None,
    state: dict[str, Any] | None = None,
    extracted_table: Any | None = None,
    input_file_name: str | None = None,
    column_index: int | None = None,
    header: str | None = None,
    column_values: list[Any] | None = None,
    column_values_sample: list[Any] | None = None,
    manifest: Any | None = None,
    logger: Any | None = None,
    event_emitter: Any | None = None,   # unused but included for consistency
    **_: Any,
) -> dict[str, float]:
    """
    Score headers that look like last-name columns.

    Returns a DICT so we can boost last_name and penalize first_name.
    This parallels the first-name header logic so users can easily follow it.
    """

    scores = {"first_name": 0.0, "last_name": 0.0}

    if not header:
        return scores

    # Normalize formatting into an intuitive searchable form.
    h = header.strip().lower()
    h = h.replace("_", " ").replace("-", " ").replace("/", " ").replace(".", " ")
    h = " ".join(h.split())
    compact = h.replace(" ", "")
    padded = f" {h} "

    # Clear last-name signals
    if (
        "lastname" in compact
        or "lname" in compact
        or "surname" in compact
        or "familyname" in compact
        or any(w in padded for w in (" last ", " surname ", " family "))
    ):
        if logger:
            logger.debug("Header LAST-name match: %r → %r", header, h)
        return {"first_name": -0.5, "last_name": 1.0}

    # If the header suggests "full name", treat as ambiguous.
    if "fullname" in compact or "full name" in padded:
        if logger:
            logger.debug("Header ambiguous FULL NAME: %r", header)
        return {"first_name": 0.25, "last_name": 0.25}

    # Generic "name" → weak signal for either
    if " name " in padded:
        if logger:
            logger.debug("Header generic NAME column: %r", header)
        return {"first_name": 0.25, "last_name": 0.25}

    return scores


# ---------------------------------------------------------------------------
# VALUE-BASED DETECTOR
# ---------------------------------------------------------------------------

def detect_last_name_from_values(
    *,
    run: Any | None = None,
    state: dict[str, Any] | None = None,
    extracted_table: Any | None = None,
    input_file_name: str | None = None,
    column_index: int | None = None,
    header: str | None = None,
    column_values: list[Any] | None = None,
    column_values_sample: list[Any] | None = None,
    manifest: Any | None = None,
    logger: Any | None = None,
    event_emitter: Any | None = None,
    **_: Any,
) -> float:
    """
    Score column values that *look* like last names.

    This detector returns a FLOAT (affects only last_name).

    Heuristics:
        • Multi-word names → often full names → reduces last-name confidence
        • Simple one-word tokens → potential last names
        • Known common last names → strong signal
        • “Last, First” patterns → strong last-name evidence
    """

    if not column_values_sample:
        return 0.0

    valid_strings = 0
    simple_lasts = 0
    common_hits = 0
    full_names = 0
    last_first_patterns = 0

    for value in column_values_sample:
        if not isinstance(value, str):
            continue

        cleaned = value.strip()
        if not cleaned:
            continue

        # Skip emails
        if "@" in cleaned:
            continue

        # Skip placeholders
        lowered = cleaned.lower()
        if lowered in {"n/a", "na", "none", "null", "-", "--"}:
            continue

        valid_strings += 1

        # “Last, First” → strong last-name indicator
        if "," in cleaned:
            last_first_patterns += 1
            continue

        tokens = cleaned.split()

        # Multi-token = full names ("John Smith")
        if len(tokens) >= 2:
            full_names += 1
            continue

        # Single word → candidate last name
        token = tokens[0].strip().strip(".")
        if not (2 <= len(token) <= 20):
            continue

        # Allow apostrophes / hyphens
        if not all(c.isalpha() or c in {"'", "-"} for c in token):
            continue

        simple_lasts += 1

        if token.lower().strip("'-") in COMMON_LAST_NAMES:
            common_hits += 1

    if logger:
        logger.debug(
            "Last-name value scan: valid=%d, simple=%d, common=%d, full=%d, last-first=%d",
            valid_strings, simple_lasts, common_hits, full_names, last_first_patterns
        )

    # ----------------------------
    # Scoring Decision Logic
    # ----------------------------

    # “Last, First” patterns are extremely strong indicators
    if last_first_patterns >= 2:
        return 1.0

    # Several matches in common last-name list
    if common_hits >= 3:
        return 0.9

    # Mostly simple one-token values (likely last names)
    if simple_lasts >= 3 and simple_lasts > full_names:
        return 0.75

    # Mostly multi-token → full names → not likely last-name field
    if full_names > simple_lasts and full_names >= 3:
        return -0.3

    # Moderate evidence
    if simple_lasts:
        return 0.4

    return 0.0


# ---------------------------------------------------------------------------
# TRANSFORM FUNCTION
# ---------------------------------------------------------------------------

def transform(
    *,
    run: Any | None = None,
    state: dict[str, Any] | None = None,
    row_index: int | None = None,
    field_name: str | None = None,
    value: Any = None,
    row: dict[str, Any] | None = None,
    field_config: Any | None = None,
    manifest: Any | None = None,
    logger: Any | None = None,
    event_emitter: Any | None = None,
    **_: Any,
) -> dict[str, Any]:
    """
    Standardize last names.

    Example:
        "smith" → "Smith"
        "o'brien" → "O'Brien"
        "gonzalez" → "Gonzalez"
    """

    if value in (None, ""):
        return {"last_name": None}

    text = str(value).strip()

    # Handle junk values
    if not text or text.lower() in {"n/a", "na", "none", "null", "-", "--"}:
        return {"last_name": None}

    # Title-case works well enough for last names
    standardized = text.title()

    if logger and standardized != text:
        logger.debug("Transform last_name: %r → %r", text, standardized)

    return {"last_name": standardized or None}
