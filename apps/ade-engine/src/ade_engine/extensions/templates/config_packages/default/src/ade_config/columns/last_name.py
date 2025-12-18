"""ADE column template: `last_name`

This module demonstrates:
- Registering a canonical field (`FieldDef`)
- A header-based detector (enabled by default)
- Optional examples: value-based detection, a transform, and a validator

Detector stage (pre-mapping)
----------------------------
- Called once per extracted table column.
- Return `{FIELD_NAME: score}` (0..1) or `None`.

Transform/validate stage (post-mapping)
---------------------------------------
- Transforms return a `pl.Expr`.
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
# - header_row, first_col, last_row, last_col (1-based, inclusive)
# - header_inferred (bool)
# - convenience properties: data_first_row, has_data_rows, data_row_count, col_count
# - range refs: ref, header_ref, data_ref

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

FIELD_NAME = "last_name"

_HEADER_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

HEADER_TOKEN_SETS_STRONG: list[set[str]] = [
    {"last", "name"},
    {"lastname"},
    {"lname"},
    {"surname"},
    {"family", "name"},
    {"familyname"},
]


def register(registry) -> None:
    """Register the `last_name` field and its detectors/transforms/validators."""
    registry.register_field(FieldDef(name=FIELD_NAME, label="Last Name", dtype="string"))

    # Enabled by default:
    registry.register_column_detector(detect_last_name_header_common_names, field=FIELD_NAME, priority=60)

    # Examples (uncomment to enable)
    # registry.register_column_detector(detect_last_name_values_basic, field=FIELD_NAME, priority=30)
    # registry.register_column_transform(normalize_last_name, field=FIELD_NAME, priority=0)
    # registry.register_column_validator(validate_last_name, field=FIELD_NAME, priority=0)


def detect_last_name_header_common_names(
    *,
    table: pl.DataFrame,  # Extracted table (pre-mapping; header row already applied)
    column: pl.Series,  # Current column as a Series
    column_sample: list[str],  # Trimmed, non-empty sample from this column (strings)
    column_name: str,  # Extracted column name (not canonical yet)
    column_index: int,  # 0-based index in table.columns
    header_text: str,  # Header cell text ("" if missing)
    settings,  # Engine Settings
    sheet_name: str,  # Worksheet title
    table_region: TableRegion | None,  # See `TableRegion` notes above
    table_index: int | None,  # 0-based index within the sheet
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Enabled by default.

    Purpose:
      - Match typical last-name headers ("last name", "surname", "family name", ...).
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


def detect_last_name_values_basic(
    *,
    table: pl.DataFrame,  # Extracted table (pre-mapping; header row already applied)
    column: pl.Series,  # Current column as a Series
    column_sample: list[str],  # Trimmed, non-empty sample from this column (strings)
    column_name: str,  # Extracted column name (not canonical yet)
    column_index: int,  # 0-based index in table.columns
    header_text: str,  # Header cell text ("" if missing)
    settings,  # Engine Settings
    sheet_name: str,  # Worksheet title
    table_region: TableRegion | None,  # See `TableRegion` notes above
    table_index: int | None,
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Example (disabled by default).

    Purpose:
      - Detect last-name columns from values when headers aren’t useful.
    """
    if not column_sample:
        return None

    good = 0
    total = 0
    for s in column_sample:
        total += 1
        if any(ch.isdigit() for ch in s):
            continue
        if " " in s:
            continue
        if len(s) >= 2:
            good += 1

    return {FIELD_NAME: float(good / total)}


def normalize_last_name(
    *,
    field_name: str,  # Canonical field name (post-mapping)
    table: pl.DataFrame,  # Post-mapping table
    settings,  # Engine Settings
    state: dict,  # Mutable dict shared across the run
    metadata: dict,  # Run metadata
    table_region: TableRegion | None,  # See `TableRegion` notes above
    table_index: int | None,
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> pl.Expr:
    """Example (disabled by default).

    Purpose:
      - Standardize blanks and whitespace.
    """
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()
    return pl.when(v.is_null() | (v == "")).then(pl.lit(None)).otherwise(v)


def validate_last_name(
    *,
    field_name: str,  # Canonical field name (post-mapping)
    table: pl.DataFrame,  # Post-mapping table
    settings,  # Engine Settings
    state: dict,  # Mutable dict shared across the run
    metadata: dict,  # Run metadata
    table_region: TableRegion | None,  # See `TableRegion` notes above
    table_index: int | None,
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> pl.Expr:
    """Example (disabled by default).

    Purpose:
      - Catch clearly bad data without being overly strict.
    """
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()
    return (
        pl.when(v.is_not_null() & (v != "") & (v.str.len_chars() > 80))
        .then(pl.lit("Last name is unusually long"))
        .otherwise(pl.lit(None))
    )
