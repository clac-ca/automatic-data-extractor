"""
Example: Readable email detector showing header-based and value-based heuristics.

Detectors may return:
    • A float → affects only `email`
    • A dict  → can adjust multiple scores (e.g., {"email": 1.0, "first_name": -0.5})

This example mirrors the structure of the name detectors but applies email-specific logic.
"""

from __future__ import annotations
import re
from typing import Any

# A simple, readable email pattern that catches almost all real-world emails.
# Not fully RFC-compliant (intentionally), but great for heuristics.
EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
    flags=re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# HEADER-BASED DETECTOR
# ---------------------------------------------------------------------------

def detect_email_header(
    *,
    header: str | None,
    logger=None,
    event_emitter=None,
    **_: Any,
) -> dict[str, float]:
    """
    Score headers that clearly relate to emails.

    Strong signals:
      • "email", "e-mail"
      • "mail", "contact_email"
      • "login", "username" (common in exports)
    """

    if not header:
        return {"email": 0.0, "first_name": 0.0, "last_name": 0.0}

    lowered = header.strip().lower()

    # Strong email keywords
    strong = ("email", "e-mail", "mail", "contact", "login", "username")
    if any(word in lowered for word in strong):
        logger and logger.debug("Detected email header: %r", header)
        return {"email": 1.0, "first_name": -0.5, "last_name": -0.5}

    # “name” columns are usually *not* emails
    if "name" in lowered:
        return {"email": -0.4, "first_name": 0.2, "last_name": 0.2}

    return {"email": 0.0, "first_name": 0.0, "last_name": 0.0}

# ---------------------------------------------------------------------------
# VALUE-BASED DETECTOR
# ---------------------------------------------------------------------------

def detect_email_values(
    *,
    column_values_sample: list[Any],
    logger=None,
    event_emitter=None,
    **_: Any,
) -> float:
    """
    Detect emails from sample column values.

    This detector returns a FLOAT affecting only the `email` field.

    Heuristics:
      • Mostly matching emails → strong match
      • Some matches, low noise → medium match
      • All values look like names → negative score
      • Mixed data → neutral

    A typical email detector focuses heavily on the '@' symbol and basic format.
    """

    if not column_values_sample:
        return 0.0

    email_hits = 0
    name_like = 0
    total_strings = 0

    for value in column_values_sample:
        if not isinstance(value, str):
            continue

        cleaned = value.strip()
        if not cleaned:
            continue

        total_strings += 1

        # Looks like a valid email → strong signal
        if EMAIL_RE.match(cleaned):
            email_hits += 1
            continue

        # Name-like values (letters + spaces only)
        if cleaned.replace(" ", "").isalpha():
            name_like += 1

    if total_strings == 0:
        return 0.0

    # RATIOS help avoid outliers in small samples
    hit_ratio = email_hits / total_strings
    name_ratio = name_like / total_strings

    # Mostly emails
    if hit_ratio >= 0.6 and email_hits >= 3:
        return 1.0

    # Mixed but leaning email-ish
    if hit_ratio >= 0.3 and email_hits >= 2:
        return 0.75

    # Mostly names → probably not email
    if name_ratio >= 0.6:
        return -0.4

    # A few emails but not dominant → slight boost
    if email_hits > 0:
        return 0.3

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
    Normalize emails to lowercase.

    Transform functions must always return a dict keyed by the field.
    """

    if value in (None, ""):
        return {"email": None}

    return {"email": str(value).strip().lower() or None}
