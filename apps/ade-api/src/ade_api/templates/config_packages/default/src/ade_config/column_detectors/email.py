"""
Email detector and transform.

Patterns demonstrated:
    • Header-based detector → returns dict so you can boost email and penalize other fields
    • Value-based detector  → returns float affecting only the email field
    • Transform function     → normalizes email casing and whitespace

This mirrors the structure of first_name / last_name examples so users can compare and learn.

# Quick shape of inputs (Script API v3):
#   run.run_id → "3f2b..."         run.paths.input_file → Path("input.xlsx")
#   manifest.columns.order → ["first_name", "last_name", "email"]
#   extracted_table.header_row → ["First Name", "Last Name", "Email"]
#   extracted_table.data_rows[:2] → [["Alice", "Smith", "alice@example.com"], ...]
#   column_index → 3   header → "Email"
#   column_values_sample → ["alice@example.com", "bob@acme.com"]
#   state → dict shared across detectors/transforms (cache something and reuse it)
#   logger/event_emitter → standard logger + optional config telemetry
"""

from __future__ import annotations

from typing import Any

# Basic email pattern pieces (kept simple for teaching purposes)
EMAIL_REQUIRED_CHARS = {"@", "."}

# ---------------------------------------------------------------------------
# HEADER-BASED DETECTOR
# ---------------------------------------------------------------------------

def detect_email_from_header(
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
    event_emitter: Any | None = None,   # unused but kept for parity
    **_: Any,
) -> float | dict[str, float]:
    """
    Score headers that look like email columns.

    Returns a DICT so we can push "email" up and optionally push other fields down.
    """

    scores = {"email": 0.0}

    if not header:
        return scores

    h = header.strip().lower()
    h = h.replace("_", " ").replace("-", " ").replace("/", " ").replace(".", " ")
    h = " ".join(h.split())     # collapse repeated spaces
    compact = h.replace(" ", "")
    padded = f" {h} "

    # Strong email indicators
    if (
        "email" in compact
        or "e-mail" in compact
        or "mail" in compact    # often "Email Address" → "mail address"
        or "emailaddress" in compact
        or "e mail" in padded
        or padded.strip() in {"email", "e mail", "email address"}
    ):
        if logger:
            logger.debug("Header EMAIL match: %r → %r", header, h)
        return {"email": 1.0}

    return scores


# ---------------------------------------------------------------------------
# VALUE-BASED DETECTOR
# ---------------------------------------------------------------------------

def detect_email_from_values(
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
) -> float | dict[str, float]:
    """
    Score values that look like email addresses.

    Returns a FLOAT that influences only the 'email' field.
    """

    if not column_values_sample:
        return 0.0

    valid_strings = 0
    email_like = 0
    strong_email = 0
    non_email = 0

    for value in column_values_sample:
        if not isinstance(value, str):
            continue

        cleaned = value.strip()
        if not cleaned:
            continue

        valid_strings += 1

        # Basic check: must contain '@'
        if "@" not in cleaned:
            non_email += 1
            continue

        # Very lenient email detection:
        #   - at least one character before '@'
        #   - at least one dot afterwards
        #   - no spaces
        if " " in cleaned:
            non_email += 1
            continue

        email_like += 1

        # Stronger check: detect typical username@domain.tld format
        if "." in cleaned.split("@")[-1]:
            strong_email += 1

    if logger:
        logger.debug(
            "Email value scan: valid=%d, email_like=%d, strong=%d, non=%d",
            valid_strings, email_like, strong_email, non_email
        )

    # Strong signal: many valid-looking emails
    if strong_email >= 3:
        return 1.0

    # Moderate signal
    if email_like >= 2:
        return 0.75

    # Weak evidence: at least one email-like value
    if email_like == 1:
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
    Transform emails into a normalized form.

    • Lowercase the address
    • Trim whitespace
    • Empty / junk → None

    This mirrors the first_name/last_name transform structure.
    """

    if value in (None, ""):
        return {"email": None}

    text = str(value).strip()

    if not text or "@" not in text:
        return {"email": None}

    normalized = text.lower()

    if logger and normalized != text:
        logger.debug("Transform email: %r → %r", text, normalized)

    return {"email": normalized}
