"""
Simple, universal data-row heuristics.

We return tiny score deltas; the engine sums them.
Add new rules by defining more `detect_*` functions with the same signature.

Signals we use:
  1) MIXED TYPES: real records often mix text and numbers
  2) VALUE PATTERNS: email, phone, SIN (9-digit Luhn) → data-like
  3) NOT BLANK: spacer rows are not data
  4) AGGREGATE PENALTY: 'total' / 'subtotal' rows are likely summaries
"""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
PHONE_RE = re.compile(r"^\s*(\+?\d[\d\-\s().]{7,}\d)\s*$")  # simple, NA/E.164-ish
AGG_WORDS = {"total", "subtotal", "grand total", "summary", "average", "avg"}

def detect_mixed_text_and_numbers(
    *,
    job, state, row_index: int, row_values: list, logger=None, **_
) -> dict:
    """
    Strong signal: data rows often have BOTH text and numbers.
    """
    non_blank = [v for v in row_values if v not in (None, "")]
    if not non_blank:
        return {"scores": {"data": 0.0}}

    has_text = any(isinstance(v, str) for v in non_blank)

    def looks_number_like(x) -> bool:
        if isinstance(x, (int, float)):
            return True
        if isinstance(x, str):
            s = x.strip()
            if not s:
                return False
            s = s.replace(",", "").replace("$", "").replace("£", "").replace("€", "")
            if s.startswith("(") and s.endswith(")"):
                s = "-" + s[1:-1]
            s = s.replace(".", "", 1).lstrip("-")
            return s.isdigit()
        return False

    has_number = any(looks_number_like(v) for v in non_blank)

    if has_text and has_number:
        score = 0.40
    elif has_number:          # numeric-only rows can still be data (e.g., metrics)
        score = 0.20
    elif has_text:            # text-only rows (names/emails) still get a small nudge
        score = 0.10
    else:
        score = 0.0
    return {"scores": {"data": score}}


def detect_value_patterns(
    *,
    job, state, row_index: int, row_values: list, logger=None, **_
) -> dict:
    """
    Strong signal: look for concrete value shapes common in real records:
      - email address
      - phone number (loose North America / E.164-ish)
      - valid 9-digit SIN (Luhn checksum)
    """
    non_blank = [v for v in row_values if v not in (None, "")]
    if not non_blank:
        return {"scores": {"data": 0.0}}

    has_email = any(isinstance(v, str) and EMAIL_RE.match(v.strip()) for v in non_blank)
    has_phone = any(isinstance(v, str) and PHONE_RE.match(v) for v in non_blank)

    # Inline Luhn check for 9-digit Canadian SIN
    def looks_valid_sin(x) -> bool:
        # Pull digits only; SIN should be exactly 9 digits
        s = "".join(ch for ch in (str(x) if x is not None else "") if ch.isdigit())
        if len(s) != 9 or len(set(s)) == 1:  # reject 000000000 / 111111111
            return False
        # Luhn algorithm
        total = 0
        # Double every second digit from the right (positions 2,4,6,8)
        for i, ch in enumerate(reversed(s), start=1):
            d = int(ch)
            if i % 2 == 0:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0

    has_sin = any(looks_valid_sin(v) for v in non_blank)

    # Base score if any pattern hits; small bonus for multiple patterns
    hits = sum([has_email, has_phone, has_sin])
    if hits == 0:
        score = 0.0
    elif hits == 1:
        score = 0.35
    elif hits == 2:
        score = 0.45
    else:
        score = 0.55
    return {"scores": {"data": score}}
