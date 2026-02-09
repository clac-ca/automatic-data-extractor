"""
ADE column template.

Conventions
-----------
- The engine calls ``register(registry)`` to register the canonical field and any callbacks.
- Detectors (pre-mapping) are invoked once per extracted table column and return
  ``{field_name: score}`` or ``None`` to abstain. ``score`` may be any float; higher values
  indicate a stronger match signal and negative values indicate counter-evidence. The
  effective scale is up to the developer.

Post-mapping (optional)
-----------------------
- Transforms return a ``pl.Expr`` (or ``None`` for a no-op).
- Validators return a ``pl.Expr`` that yields a per-row message (string) or null.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING, Any

import polars as pl
from ade_engine.models import FieldDef

if TYPE_CHECKING:
    from ade_engine.extensions.registry import Registry
    from ade_engine.infrastructure.observability.logger import RunLogger
    from ade_engine.infrastructure.settings import Settings
    from ade_engine.models import TableRegion


def register(registry: Registry) -> None:
    """Register the `full_name` field and its detectors/transforms/validators."""
    registry.register_field(FieldDef(name="full_name", label="Full Name", dtype="string"))
    registry.register_column_detector(
        detect_full_name_header_common_names, field="full_name", priority=60
    )
    registry.register_column_transform(normalize_full_name, field="full_name", priority=0)

    # Examples (uncomment to enable)
    # registry.register_column_detector(detect_full_name_values_basic, field="full_name", priority=30)
    # registry.register_column_validator(validate_full_name, field="full_name", priority=0)


def detect_full_name_header_common_names(
    *,
    table: pl.DataFrame,  # Extracted table (pre-mapping; header row already applied)
    column: pl.Series,  # Current column as a Series
    column_sample_non_empty_values: list[
        str
    ],  # Trimmed, non-empty sample from this column (strings)
    column_name: str,  # Extracted column name (not canonical yet)
    column_index: int,  # 0-based index in table.columns
    field_name: str,  # Canonical field name (registered for this detector)
    column_header_original: str,  # Header cell text ("" if missing)
    settings: Settings,  # Engine Settings
    sheet_name: str,  # Worksheet title
    table_region: TableRegion,  # Excel coords via .min_row/.max_row/.min_col/.max_col; helpers .a1/.header_row/.data_first_row
    table_index: int,
    metadata: Mapping[str, Any],  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: MutableMapping[str, Any],  # Mutable dict shared across the run
    input_file_name: str,  # Input filename (basename)
    logger: RunLogger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Enabled by default.

    Purpose:
      - Match common headers for full_name (strong and weak variants).
      - Keep it simple and predictable.
    """
    header_non_alnum_re = re.compile(r"[^a-z0-9]+")

    # Full name can be labeled many ways.
    # We give strong score to "full name" and similar, and a weaker score for plain "name".
    header_token_sets_strong: list[set[str]] = [
        {"full", "name"},
        {"fullname"},
        {"employee", "name"},
        {"person", "name"},
        {"worker", "name"},
        {"member", "name"},
    ]
    header_token_sets_weak: list[set[str]] = [
        {"name"},  # very common but ambiguous
    ]

    raw = (column_header_original or "").strip().lower()
    if not raw:
        return None

    normalized = header_non_alnum_re.sub(" ", raw).strip()
    tokens = set(normalized.split())
    if not tokens:
        return None

    if any(pattern <= tokens for pattern in header_token_sets_strong):
        return {"full_name": 1.0}

    if any(pattern <= tokens for pattern in header_token_sets_weak):
        return {"full_name": 0.8}

    return None


def detect_full_name_values_basic(
    *,
    table: pl.DataFrame,  # Extracted table (pre-mapping; header row already applied)
    column: pl.Series,  # Current column as a Series
    column_sample_non_empty_values: list[
        str
    ],  # Trimmed, non-empty sample from this column (strings)
    column_name: str,  # Extracted column name (not canonical yet)
    column_index: int,  # 0-based index in table.columns
    field_name: str,  # Canonical field name (registered for this detector)
    column_header_original: str,  # Header cell text ("" if missing)
    settings: Settings,  # Engine Settings
    sheet_name: str,  # Worksheet title
    table_region: TableRegion,  # See `TableRegion` notes above
    table_index: int,
    metadata: Mapping[str, Any],  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: MutableMapping[str, Any],  # Mutable dict shared across the run
    input_file_name: str,  # Input filename (basename)
    logger: RunLogger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Example (disabled by default).

    Purpose:
      - Detect full names by looking at values:
        - "First Last" OR "Last, First"
      - Skip values that contain digits (often IDs).
    """
    comma_name_re = re.compile(r"^[A-Za-z][\w'\-]*,\s*[A-Za-z][\w'\-]*$")
    space_name_re = re.compile(r"^[A-Za-z][\w'\-]*\s+[A-Za-z][\w'\-]*$")

    if not column_sample_non_empty_values:
        return None

    matches = 0
    total = 0

    for s in column_sample_non_empty_values:
        if any(ch.isdigit() for ch in s):
            continue
        total += 1
        if comma_name_re.fullmatch(s) or space_name_re.fullmatch(s):
            matches += 1

    if total == 0:
        return None

    return {"full_name": float(matches / total)}


def normalize_full_name(
    *,
    field_name: str,  # Canonical field name (post-mapping)
    table: pl.DataFrame,  # Post-mapping table
    table_region: TableRegion,  # Source table coordinates (1-based, inclusive)
    table_index: int,  # 0-based table index within the sheet
    input_file_name: str,  # Input filename (basename)
    settings: Settings,  # Engine Settings
    metadata: Mapping[str, Any],  # Run metadata
    state: MutableMapping[str, Any],  # Mutable dict shared across the run
    logger: RunLogger,  # RunLogger (structured events + text logs)
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

    derived_first = (
        pl.when(derived_first.is_null() | (derived_first == ""))
        .then(pl.lit(None))
        .otherwise(derived_first)
    )
    derived_last = (
        pl.when(derived_last.is_null() | (derived_last == ""))
        .then(pl.lit(None))
        .otherwise(derived_last)
    )

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
    settings: Settings,  # Engine Settings
    metadata: Mapping[str, Any],  # Run metadata
    state: MutableMapping[str, Any],  # Mutable dict shared across the run
    logger: RunLogger,  # RunLogger (structured events + text logs)
) -> pl.Expr:
    """Example (disabled by default).

    Purpose:
      - Flag unexpected characters.
      - Show a simple cross-field consistency check (if first+last exist but full is missing).
    """
    allowed_full_name_pattern = r"^[A-Za-z][A-Za-z '\-]*$"
    v = pl.col(field_name).cast(pl.Utf8, strict=False).str.strip_chars()

    format_issue = (
        pl.when(v.is_not_null() & (v != "") & ~v.str.contains(allowed_full_name_pattern))
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
