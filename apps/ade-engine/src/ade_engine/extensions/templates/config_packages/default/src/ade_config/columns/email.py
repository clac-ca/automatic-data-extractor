"""ADE column template: `email`

This module demonstrates:
- Registering a canonical field (`FieldDef`)
- A header-based column detector (enabled by default)
- Optional examples: value-based detection, a transform, and a validator

Detector stage (pre-mapping)
----------------------------
- Called once per extracted table column.
- Return `{"email": score}` (0..1) or `None`.

Transform/validate stage (post-mapping)
---------------------------------------
- Transforms return a `pl.Expr` (or `None` for no-op).
- Validators return a `pl.Expr` producing a per-row message (string) or null.

Template goals
--------------
- Keep the default detector simple, fast, and deterministic.
- Keep examples self-contained and opt-in (uncomment in `register()`).
"""

from __future__ import annotations

import re

import polars as pl
from ade_engine.models import FieldDef, TableRegion


def register(registry) -> None:
    """Register the `email` field and its detectors/transforms/validators."""
    registry.register_field(FieldDef(name="email", label="Email", dtype="string"))

    # Enabled by default: detect "email" using common header names.
    registry.register_column_detector(detect_email_header_common_names, field="email", priority=60)

    # Examples (uncomment to enable)
    # registry.register_column_detector(detect_email_values_sample_regex, field="email", priority=30)
    # registry.register_column_transform(normalize_email, field="email", priority=0)
    # registry.register_column_validator(validate_email, field="email", priority=0)


def detect_email_header_common_names(
    *,
    table: pl.DataFrame,  # Extracted table (pre-mapping; header row already applied)
    column: pl.Series,  # Current column as a Series
    column_sample: list[str],  # Trimmed, non-empty sample from this column (strings)
    column_name: str,  # Current table column name (extracted header; not canonical)
    column_index: int,  # 0-based index in table.columns
    header_text: str,  # Header cell text for this column ("" if missing)
    settings,  # Engine settings object
    sheet_name: str,  # Sheet title
    table_region: TableRegion,  # Excel coords via .min_row/.max_row/.min_col/.max_col; helpers .a1/.header_row/.data_first_row
    table_index: int,
    metadata: dict,  # Run metadata
    state: dict,  # Shared mutable run state
    input_file_name: str,  # Input filename (basename)
    logger,  # Logger
) -> dict[str, float] | None:
    """Enabled by default.

    Purpose:
      - Teach the simplest reliable detector: header-based matching.
      - Works well when spreadsheets have reasonable headers.
    """
    # Keep matching configuration close to the detector (this is a teaching template).
    header_non_alnum_re = re.compile(r"[^a-z0-9]+")
    header_token_sets_strong: list[set[str]] = [
        {"email"},
        {"e", "mail"},
        {"emailaddress"},  # some files use "emailaddress" with no separator
        {"emailid"},  # "emailid"
    ]

    raw = (header_text or "").strip().lower()
    if not raw:
        return None

    normalized = header_non_alnum_re.sub(" ", raw).strip()
    tokens = set(normalized.split())
    if not tokens:
        return None

    if any(pattern <= tokens for pattern in header_token_sets_strong):
        return {"email": 1.0}

    return None


def detect_email_values_sample_regex(
    *,
    table: pl.DataFrame,  # Extracted table (pre-mapping; header row already applied)
    column: pl.Series,  # Current column as a Series
    column_sample: list[str],  # Trimmed, non-empty sample from this column (strings)
    column_name: str,  # Extracted column name (not canonical yet)
    column_index: int,  # 0-based index in table.columns
    header_text: str,  # Header cell text ("" if missing)
    settings,  # Engine Settings
    sheet_name: str,  # Worksheet title
    table_region: TableRegion,  # See `TableRegion` notes above
    table_index: int,
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    input_file_name: str,  # Input filename (basename)
    logger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Example (disabled by default).

    Purpose:
      - Detect email columns by looking at values (useful when headers are missing).
    """
    email_pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    email_re = re.compile(email_pattern)

    if not column_sample:
        return None

    matches = 0
    total = 0
    for s in column_sample:
        total += 1
        if email_re.fullmatch(s.strip().lower()):
            matches += 1

    return {"email": float(matches / total)}


def normalize_email(
    *,
    field_name: str,  # Canonical field name (post-mapping)
    table: pl.DataFrame,  # Post-mapping table
    table_region: TableRegion,  # Source table coordinates (1-based, inclusive)
    table_index: int,  # 0-based table index within the sheet
    input_file_name: str,  # Input filename (basename)
    settings,  # Engine Settings
    metadata: dict,  # Run metadata
    state: dict,  # Mutable dict shared across the run
    logger,  # RunLogger (structured events + text logs)
) -> pl.Expr:
    """Example (disabled by default).

    Purpose:
      - Normalize formatting so downstream systems get consistent casing/whitespace.

    Notes:
      - Returns a `pl.Expr` (a deferred, vectorized column expression).
      - The engine will alias the expression to `field_name`.
    """
    raw = pl.col(field_name).cast(pl.Utf8, strict=False)

    # Email normalization is usually safe to do aggressively:
    # - trim whitespace
    # - lowercase
    # - empty -> null
    text = raw.str.strip_chars().str.to_lowercase()
    return pl.when(text.is_null() | (text == "")).then(pl.lit(None)).otherwise(text)


def validate_email(
    *,
    field_name: str,  # Canonical field name (post-mapping)
    table: pl.DataFrame,  # Post-mapping table
    table_region: TableRegion,  # Source table coordinates (1-based, inclusive)
    table_index: int,  # 0-based table index within the sheet
    input_file_name: str,  # Input filename (basename)
    settings,  # Engine Settings
    metadata: dict,  # Run metadata
    state: dict,  # Mutable dict shared across the run
    logger,  # RunLogger (structured events + text logs)
) -> pl.Expr:
    """Example (disabled by default).

    Purpose:
      - Emit a per-row message when an email is present but invalid.

    Return value:
      - Message string when invalid, else null (stored in `__ade_issue__{field_name}`).
    """
    email_pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    v = pl.col(field_name).cast(pl.Utf8, strict=False).str.strip_chars().str.to_lowercase()
    return (
        pl.when(v.is_not_null() & (v != "") & ~v.str.contains(email_pattern))
        .then(pl.concat_str([pl.lit("Invalid email: "), v]))
        .otherwise(pl.lit(None))
    )
