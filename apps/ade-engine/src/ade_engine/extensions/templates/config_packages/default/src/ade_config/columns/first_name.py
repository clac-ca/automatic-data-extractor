"""ADE column template: `first_name`

This module demonstrates:
- Registering a canonical field (`FieldDef`)
- A header-based detector (enabled by default)
- Optional examples: value-based detection, neighbor-based detection, a transform, and a validator

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

FIELD_NAME = "first_name"

_HEADER_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

HEADER_TOKEN_SETS_STRONG: list[set[str]] = [
    {"first", "name"},
    {"firstname"},
    {"fname"},
    {"given", "name"},
    {"givenname"},
    {"forename"},
]


def register(registry) -> None:
    """Register the `first_name` field and its detectors/transforms/validators."""
    registry.register_field(FieldDef(name=FIELD_NAME, label="First Name", dtype="string"))

    # Enabled by default:
    # Detect "first_name" using common header names.
    registry.register_column_detector(detect_first_name_header_common_names, field=FIELD_NAME, priority=60)

    # Examples (uncomment to enable)
    # registry.register_column_detector(detect_first_name_values_basic, field=FIELD_NAME, priority=30)
    # registry.register_column_detector(detect_first_name_values_neighbor_pair, field=FIELD_NAME, priority=25)
    # registry.register_column_transform(normalize_first_name, field=FIELD_NAME, priority=0)
    # registry.register_column_validator(validate_first_name, field=FIELD_NAME, priority=0)


def detect_first_name_header_common_names(
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
    table_index: int,  # 0-based index within the sheet (when multiple tables exist)
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    input_file_name: str,  # Input filename (basename)
    logger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Enabled by default.

    Purpose:
      - Match typical first-name headers ("first name", "fname", "given name", ...).
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


def detect_first_name_values_basic(
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
      - Detect first-name columns from values when headers aren’t useful.
      - Simple heuristic: short, single-token, non-numeric strings.
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
        if 2 <= len(s) <= 20:
            good += 1

    return {FIELD_NAME: float(good / total)}


def detect_first_name_values_neighbor_pair(
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
      - Demonstrate cross-column detection when canonical names are unknown.
      - Uses column_index to look at the *right neighbor* (common layout: First | Last).

    Note:
      - We do not reference "last_name" here because mapping hasn't happened yet.
    """
    if not column_sample:
        return None

    # Base score from this column's sample.
    base_good = 0
    base_total = 0
    for s in column_sample:
        base_total += 1
        if any(ch.isdigit() for ch in s) or " " in s or not (2 <= len(s) <= 20):
            continue
        base_good += 1
    base_score = base_good / base_total

    # Neighbor score from the right column (sampled from the table).
    if column_index + 1 >= len(table.columns):
        return {FIELD_NAME: float(base_score)}

    row_n = settings.detectors.row_sample_size
    text_n = settings.detectors.text_sample_size

    t = table.head(row_n)
    right_col_name = t.columns[column_index + 1]
    right_series = t.get_column(right_col_name)

    right_sample: list[str] = []
    for v in right_series.to_list():
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        right_sample.append(s)
        if len(right_sample) >= text_n:
            break

    if not right_sample:
        return {FIELD_NAME: float(base_score)}

    right_good = 0
    right_total = 0
    for s in right_sample:
        right_total += 1
        if any(ch.isdigit() for ch in s) or " " in s or not (2 <= len(s) <= 20):
            continue
        right_good += 1
    right_score = right_good / right_total

    # Boost only when both columns look strongly "name-ish".
    score = float(base_score)
    if base_score >= 0.7 and right_score >= 0.7:
        score = min(1.0, score + 0.15)

    return {FIELD_NAME: score}


def normalize_first_name(
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
      - Returns a `pl.Expr`, which is a *deferred* expression (a recipe for a column).
      - The engine will apply it to the DataFrame and alias it to `field_name`.
      - Use `pl.lit(...)` for literals (including strings and `None`).
    """
    raw = pl.col(field_name).cast(pl.Utf8, strict=False)

    # Step 1: normalize whitespace.
    text = raw.str.strip_chars().str.replace_all(r"\s+", " ")

    # Step 2: normalize empty strings to null.
    normalized = pl.when(text.is_null() | (text == "")).then(pl.lit(None)).otherwise(text)
    return normalized


def validate_first_name(
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
      - A `pl.Expr` that yields a message string when invalid, else null.
      - ADE stores the result in `__ade_issue__{field_name}`.
    """
    v = pl.col(field_name).cast(pl.Utf8, strict=False).str.strip_chars()
    return (
        pl.when(v.is_not_null() & (v != "") & (v.str.len_chars() > 50))
        .then(pl.lit("First name is unusually long"))
        .otherwise(pl.lit(None))
    )
