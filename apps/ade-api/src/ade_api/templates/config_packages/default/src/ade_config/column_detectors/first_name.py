"""
Example: Readable first-name detector showing BOTH return styles.

Detectors may return:
    • A float → applies only to the field being detected (e.g., 0.8 for first_name)
    • A dict  → lets you influence multiple fields (e.g., {"first_name": 1.0, "last_name": -0.5})

This example:
    ✔ Shows both return patterns
    ✔ Keeps all parameters in the signature so users see the full real-world shape
    ✔ Avoids abstractions and helper functions to stay intuitive
    ✔ Includes inline commentary to help new authors learn how to build detectors
"""

from __future__ import annotations

from typing import Any

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
    event_emitter: Any | None = None,   # included even if not used
    **_: Any,
) -> dict[str, float]:
    """
    Score headers that look like first-name columns.

    This detector returns a DICT so it can:
        • Boost first_name
        • Penalize last_name (or vice-versa)

    Full signature is shown because real detectors receive many arguments.
    Even though some aren't used here, keeping them helps readers understand
    what they have access to when they write their own detectors.
    """

    # Default neutral scoring
    scores = {"first_name": 0.0, "last_name": 0.0}

    if not header:
        return scores

    # Make the header easier to compare across formats:
    #   "FirstName" → "first name"
    #   "first_name" → "first name"
    h = header.strip().lower()
    h = h.replace("_", " ").replace("-", " ").replace("/", " ").replace(".", " ")
    h = " ".join(h.split())     # collapse repeated spaces
    compact = h.replace(" ", "")  # catching "firstname" / "lastname" variants
    padded = f" {h} "            # cheap way to check word boundaries

    # Strong signals of FIRST NAME
    if (
        "firstname" in compact
        or "fname" in compact
        or "givenname" in compact
        or any(w in padded for w in (" first ", " given ", " forename "))
    ):
        if logger:
            logger.debug("Header FIRST-name match: %r → %r", header, h)
        return {"first_name": 1.0, "last_name": -0.5}

    # Strong signals of LAST NAME
    if (
        "lastname" in compact
        or "lname" in compact
        or any(w in padded for w in (" last ", " surname ", " family "))
    ):
        if logger:
            logger.debug("Header LAST-name match: %r → %r", header, h)
        return {"first_name": -0.5, "last_name": 1.0}

    # Generic "name" field → ambiguous
    if " name " in padded or "fullname" in compact:
        if logger:
            logger.debug("Header ambiguous NAME column: %r → %r", header, h)
        return {"first_name": 0.25, "last_name": 0.25}

    return scores


# ---------------------------------------------------------------------------
# VALUE-BASED DETECTOR
# ---------------------------------------------------------------------------

def detect_first_name_from_values(
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
    event_emitter: Any | None = None,   # unused but included
    **_: Any,
) -> float:
    """
    Score column values that *look* like first names.

    This detector returns a FLOAT — boosting only first_name.

    Heuristics:
        • One-token names are good candidates
        • Known common names produce strong signals
        • Comma-separated or multi-word entries tend to be full names → penalize
    """

    if not column_values_sample:
        return 0.0

    valid_strings = 0
    simple_firsts = 0
    common_hits = 0
    full_names = 0

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
        if cleaned.lower() in {"n/a", "na", "none", "null", "-", "--"}:
            continue

        valid_strings += 1

        # "Last, First"
        if "," in cleaned:
            full_names += 1
            continue

        tokens = cleaned.split()

        # Multi-word name
        if len(tokens) >= 2:
            full_names += 1
            continue

        # "Anne-Marie", "O'Neil" etc.
        token = tokens[0].strip().strip(".")
        if not (2 <= len(token) <= 14):
            continue

        if not all(c.isalpha() or c in {"'", "-"} for c in token):
            continue

        simple_firsts += 1

        key = token.lower().strip("'-")
        if key in COMMON_FIRST_NAMES:
            common_hits += 1

    if logger:
        logger.debug(
            "Value pattern summary: valid=%d, simple=%d, common=%d, full=%d",
            valid_strings, simple_firsts, common_hits, full_names
        )

    # Decision rules
    if common_hits >= 3:
        return 1.0

    if simple_firsts >= 3 and simple_firsts > full_names:
        return 0.75

    if full_names > simple_firsts:
        return -0.3

    if simple_firsts:
        return 0.4

    return 0.0


# ---------------------------------------------------------------------------
# VALUE SHAPE DETECTOR (stub example)
# ---------------------------------------------------------------------------

def detect_value_shape(
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
) -> dict:
    """
    Example placeholder showing how a shape-based detector *would* fit in.

    This detector returns a dict so it can influence multiple fields
    (if someone wanted to detect general structure like:
         • "everything looks numeric"
         • "everything looks like dates"
         • "everything looks like single short tokens"
    )

    This stub does nothing but shows authors the full template.
    """
    if logger:
        logger.debug("Running detect_value_shape() on column %d", column_index)

    # A shape detector would normally analyze:
    #   - length consistencies
    #   - digit ratios
    #   - pattern regularity
    #   - etc.
    # Returning a neutral dict keeps this as an example.
    return {"first_name": 0.0, "last_name": 0.0}


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
    Example transform: clean and standardize first names.
    """

    if value in (None, ""):
        return {"first_name": None}

    text = str(value).strip()
    if not text:
        return {"first_name": None}

    standardized = text.title()

    if logger and standardized != text:
        logger.debug("Transform: %r → %r", text, standardized)

    return {"first_name": standardized or None}
