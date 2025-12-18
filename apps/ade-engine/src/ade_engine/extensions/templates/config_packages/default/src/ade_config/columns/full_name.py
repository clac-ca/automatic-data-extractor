"""ADE column template: `full_name`

This module demonstrates:
- Registering a canonical field (`FieldDef`)
- A header-based detector (enabled by default)
- A per-column transform (enabled by default)
- Optional examples: value-based detection and a validator with a simple cross-field check

Detector stage (pre-mapping)
----------------------------
- Called once per extracted table column.
- Return `{FIELD_NAME: score}` (0..1) or `None`.

Transform/validate stage (post-mapping)
---------------------------------------
- Transforms return a `pl.Expr` (or `None` for no-op).
- Validators return a `pl.Expr` producing a per-row message (string) or null.
- For derived columns (e.g., split `full_name` into `first_name`/`last_name`), use a table hook (see `ade_config/hooks/on_table_mapped.py`).

Template goals
--------------
- Keep the default detector simple, fast, and deterministic.
- Keep examples self-contained and opt-in (uncomment in `register()`).
- This file intentionally enables one transform to demonstrate per-column transforms.
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

FIELD_NAME = "full_name"

_HEADER_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# Full name can be labeled many ways.
# We give strong score to "full name" and similar, and a weaker score for plain "name".
HEADER_TOKEN_SETS_STRONG: list[set[str]] = [
    {"full", "name"},
    {"fullname"},
    {"employee", "name"},
    {"person", "name"},
    {"worker", "name"},
    {"member", "name"},
]

HEADER_TOKEN_SETS_WEAK: list[set[str]] = [
    {"name"},  # very common but ambiguous
]

# Simple "looks like a name" patterns for value-based example.
COMMA_NAME_RE = re.compile(r"^[A-Za-z][\w'\-]*,\s*[A-Za-z][\w'\-]*$")
SPACE_NAME_RE = re.compile(r"^[A-Za-z][\w'\-]*\s+[A-Za-z][\w'\-]*$")

ALLOWED_FULL_NAME_PATTERN = r"^[A-Za-z][A-Za-z '\-]*$"


def register(registry) -> None:
    """Register the `full_name` field and its detectors/transforms/validators."""
    registry.register_field(FieldDef(name=FIELD_NAME, label="Full Name", dtype="string"))

    # Enabled by default:
    registry.register_column_detector(detect_full_name_header_common_names, field=FIELD_NAME, priority=60)
    registry.register_column_transform(normalize_full_name, field=FIELD_NAME, priority=0)

    # Examples (uncomment to enable)
    # registry.register_column_detector(detect_full_name_values_basic, field=FIELD_NAME, priority=30)
    # registry.register_column_validator(validate_full_name, field=FIELD_NAME, priority=0)


def detect_full_name_header_common_names(
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
    """Enabled by default.

    Purpose:
      - Match common headers for full_name (strong and weak variants).
      - Keep it simple and predictable.
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

    if any(pattern <= tokens for pattern in HEADER_TOKEN_SETS_WEAK):
        return {FIELD_NAME: 0.8}

    return None


def detect_full_name_values_basic(
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
      - Detect full names by looking at values:
        - "First Last" OR "Last, First"
      - Skip values that contain digits (often IDs).
    """
    if not column_sample:
        return None

    matches = 0
    total = 0

    for s in column_sample:
        if any(ch.isdigit() for ch in s):
            continue
        total += 1
        if COMMA_NAME_RE.fullmatch(s) or SPACE_NAME_RE.fullmatch(s):
            matches += 1

    if total == 0:
        return None

    return {FIELD_NAME: float(matches / total)}


def normalize_full_name(
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
    """Enabled by default.

    Purpose:
      - Demonstrate a per-column transform (single-output).
      - Normalize common full-name formats:
        - "Last, First" -> "First Last"
        - collapse internal whitespace
        - convert empty strings to null

    Notes:
      - Returns a `pl.Expr` (a deferred, vectorized column expression).
      - This is a slightly more advanced example: it uses Polars list operations
        (`str.split(...).list.get(...)`) to extract name parts.
    """
    full = pl.col(field_name).cast(pl.Utf8, strict=False).str.strip_chars()
    full = full.str.replace_all(r"\s+", " ")
    full = pl.when(full.is_null() | (full == "")).then(pl.lit(None)).otherwise(full)

    has_comma = full.str.contains(",")

    # "Last, First" -> split on comma and pick both sides.
    comma_parts = full.str.split(",")
    comma_last = comma_parts.list.get(0, null_on_oob=True).cast(pl.Utf8).str.strip_chars()
    comma_first = comma_parts.list.get(1, null_on_oob=True).cast(pl.Utf8).str.strip_chars()

    # "First Last" -> split on spaces and pick the first and last tokens.
    space_parts = full.str.split(" ")
    space_len = space_parts.list.len()
    space_first = space_parts.list.get(0, null_on_oob=True).cast(pl.Utf8).str.strip_chars()
    space_last = (
        pl.when(space_len >= 2)
        .then(space_parts.list.get(-1, null_on_oob=True).cast(pl.Utf8).str.strip_chars())
        .otherwise(pl.lit(None))
    )

    derived_first = pl.when(has_comma).then(comma_first).otherwise(space_first)
    derived_last = pl.when(has_comma).then(comma_last).otherwise(space_last)

    derived_first = pl.when(derived_first.is_null() | (derived_first == "")).then(pl.lit(None)).otherwise(derived_first)
    derived_last = pl.when(derived_last.is_null() | (derived_last == "")).then(pl.lit(None)).otherwise(derived_last)

    normalized_full = (
        pl.when(derived_first.is_not_null() & derived_last.is_not_null())
        .then(pl.concat_str([derived_first, derived_last], separator=" "))
        .otherwise(full)
    )

    return normalized_full


def validate_full_name(
    *,
    field_name: str,  # Canonical field name (post-mapping)
    table: pl.DataFrame,  # Post-mapping table (so validators can reference other fields)
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
      - Flag unexpected characters.
      - Show a simple cross-field consistency check (if first+last exist but full is missing).
    """
    v = pl.col(field_name).cast(pl.Utf8, strict=False).str.strip_chars()

    format_issue = (
        pl.when(v.is_not_null() & (v != "") & ~v.str.contains(ALLOWED_FULL_NAME_PATTERN))
        .then(pl.lit("Full name contains unexpected characters"))
        .otherwise(pl.lit(None))
    )

    if "first_name" in table.columns and "last_name" in table.columns:
        first = pl.col("first_name").cast(pl.Utf8, strict=False).str.strip_chars()
        last = pl.col("last_name").cast(pl.Utf8, strict=False).str.strip_chars()

        missing_full = v.is_null() | (v == "")
        parts_present = first.is_not_null() & (first != "") & last.is_not_null() & (last != "")

        parts_issue = (
            pl.when(missing_full & parts_present)
            .then(pl.lit("Full name is missing but first/last are present"))
            .otherwise(pl.lit(None))
        )

        return pl.coalesce([format_issue, parts_issue])

    return format_issue
