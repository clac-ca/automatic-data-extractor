"""ADE column template: `email`

This module demonstrates:
- Registering a canonical field (`FieldDef`)
- A header-based column detector (enabled by default)
- Optional examples: value-based detection, a transform, and a validator

Detector stage (pre-mapping)
----------------------------
- Called once per extracted table column.
- Return `{FIELD_NAME: score}` (0..1) or `None`.

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

# `TableRegion` (engine-owned, openpyxl-friendly coordinates):
# - min_row, min_col, max_row, max_col (1-based, inclusive)
# - convenience properties: a1, cell_range, width, height
# - header/data helpers: header_row, data_first_row, data_min_row, has_data_rows, data_row_count

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


# -----------------------------------------------------------------------------
# Field + header-name matching configuration
# -----------------------------------------------------------------------------

FIELD_NAME = "email"

# Normalize header text to tokens by:
# - lowercasing
# - replacing non-alphanumerics with spaces (so "e-mail" -> "e mail", "email_address" -> "email address")
# - splitting into tokens
_HEADER_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# Enabled-by-default detection uses token sets.
# If any set is a subset of the header tokens, we match.
HEADER_TOKEN_SETS_STRONG: list[set[str]] = [
    {"email"},
    {"e", "mail"},
    {"emailaddress"},   # some files use "emailaddress" with no separator
    {"emailid"},        # "emailid"
]

# Optional: keep a stricter pattern around for value-based examples.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
EMAIL_RE = re.compile(EMAIL_PATTERN)


def register(registry) -> None:
    """Register the `email` field and its detectors/transforms/validators."""
    registry.register_field(FieldDef(name=FIELD_NAME, label="Email", dtype="string"))

    # Enabled by default: detect "email" using common header names.
    registry.register_column_detector(detect_email_header_common_names, field=FIELD_NAME, priority=60)

    # Examples (uncomment to enable)
    # registry.register_column_detector(detect_email_values_sample_regex, field=FIELD_NAME, priority=30)
    # registry.register_column_transform(normalize_email, field=FIELD_NAME, priority=0)
    # registry.register_column_validator(validate_email, field=FIELD_NAME, priority=0)


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
    table_region: TableRegion,  # See `TableRegion` notes above
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
    raw = (header_text or "").strip().lower()
    if not raw:
        return None

    normalized = _HEADER_NON_ALNUM_RE.sub(" ", raw).strip()
    tokens = set(normalized.split())
    if not tokens:
        return None

    if any(pattern <= tokens for pattern in HEADER_TOKEN_SETS_STRONG):
        return {FIELD_NAME: 1.0}

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
    if not column_sample:
        return None

    matches = 0
    total = 0
    for s in column_sample:
        total += 1
        if EMAIL_RE.fullmatch(s.strip().lower()):
            matches += 1

    return {FIELD_NAME: float(matches / total)}


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
    v = pl.col(field_name).cast(pl.Utf8, strict=False).str.strip_chars().str.to_lowercase()
    return (
        pl.when(v.is_not_null() & (v != "") & ~v.str.contains(EMAIL_PATTERN))
        .then(pl.concat_str([pl.lit("Invalid email: "), v]))
        .otherwise(pl.lit(None))
    )
