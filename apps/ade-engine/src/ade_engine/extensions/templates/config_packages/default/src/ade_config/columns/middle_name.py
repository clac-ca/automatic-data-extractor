"""ADE column template: `middle_name`

This module demonstrates:
- Registering a canonical field (`FieldDef`)
- A header-based detector (enabled by default)
- Optional examples: value-based detection, a transform, and a validator

Detector stage (pre-mapping)
----------------------------
- Called once per extracted table column.
- Return `{"middle_name": score}` (0..1) or `None`.

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


def register(registry) -> None:
    """Register the `middle_name` field and its detectors/transforms/validators."""
    registry.register_field(FieldDef(name="middle_name", label="Middle Name", dtype="string"))

    # Enabled by default:
    registry.register_column_detector(
        detect_middle_name_header_common_names, field="middle_name", priority=60
    )

    # Examples (uncomment to enable)
    # registry.register_column_detector(detect_middle_name_values_initials, field="middle_name", priority=30)
    # registry.register_column_transform(normalize_middle_name, field="middle_name", priority=0)
    # registry.register_column_validator(validate_middle_name, field="middle_name", priority=0)


def detect_middle_name_header_common_names(
    *,
    table: pl.DataFrame,  # Extracted table (pre-mapping; header row already applied)
    column: pl.Series,  # Current column as a Series
    column_sample: list[str],  # Trimmed, non-empty sample from this column (strings)
    column_name: str,  # Extracted column name (not canonical yet)
    column_index: int,  # 0-based index in table.columns
    header_text: str,  # Header cell text ("" if missing)
    settings,  # Engine Settings
    sheet_name: str,  # Worksheet title
    table_region: TableRegion,  # Excel coords via .min_row/.max_row/.min_col/.max_col; helpers .a1/.header_row/.data_first_row
    table_index: int,
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    input_file_name: str,  # Input filename (basename)
    logger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Enabled by default.

    Purpose:
      - Match typical middle-name headers ("middle name", "mi", "middle initial", ...).
    """
    header_non_alnum_re = re.compile(r"[^a-z0-9]+")
    header_token_sets_strong: list[set[str]] = [
        {"middle", "name"},
        {"middlename"},
        {"middle", "initial"},
        {"middleinitial"},
        {"mi"},
        {"m", "i"},  # supports "M.I." -> "m i"
    ]

    raw = (header_text or "").strip().lower()
    if not raw:
        return None

    normalized = header_non_alnum_re.sub(" ", raw).strip()
    tokens = set(normalized.split())
    if not tokens:
        return None

    if any(pattern <= tokens for pattern in header_token_sets_strong):
        return {"middle_name": 1.0}

    return None


def detect_middle_name_values_initials(
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
      - Recognize columns that are mostly initials: "A" or "A."
    """
    if not column_sample:
        return None

    matches = 0
    total = 0
    for s in column_sample:
        total += 1
        if len(s) == 1 and s.isalpha():
            matches += 1
        elif len(s) == 2 and s[0].isalpha() and s[1] == ".":
            matches += 1

    return {"middle_name": float(matches / total)}


def normalize_middle_name(
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
      - Standardize blanks and whitespace.

    Notes:
      - Returns a `pl.Expr` (a deferred, vectorized column expression).
      - The engine will alias the expression to `field_name`.
    """
    raw = pl.col(field_name).cast(pl.Utf8, strict=False)
    text = raw.str.strip_chars().str.replace_all(r"\s+", " ")
    return pl.when(text.is_null() | (text == "")).then(pl.lit(None)).otherwise(text)


def validate_middle_name(
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
      - Catch clearly bad data without being overly strict.

    Return value:
      - Message string when invalid, else null (stored in `__ade_issue__{field_name}`).
    """
    v = pl.col(field_name).cast(pl.Utf8, strict=False).str.strip_chars()
    return (
        pl.when(v.is_not_null() & (v != "") & (v.str.len_chars() > 40))
        .then(pl.lit("Middle name is unusually long"))
        .otherwise(pl.lit(None))
    )
