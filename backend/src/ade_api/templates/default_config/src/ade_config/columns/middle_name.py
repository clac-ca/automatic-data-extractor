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
from typing import Any, TYPE_CHECKING

import polars as pl
from ade_engine.models import FieldDef

if TYPE_CHECKING:
    from ade_engine.models import TableRegion

    from ade_engine.extensions.registry import Registry
    from ade_engine.infrastructure.observability.logger import RunLogger
    from ade_engine.infrastructure.settings import Settings


def register(registry: Registry) -> None:
    """Register the `middle_name` field and its detectors/transforms/validators."""
    registry.register_field(FieldDef(name="middle_name", label="Middle Name", dtype="string"))
    registry.register_column_detector(detect_middle_name_header_common_names, field="middle_name", priority=60)

    # Examples (uncomment to enable)
    # registry.register_column_detector(detect_middle_name_values_initials, field="middle_name", priority=30)
    # registry.register_column_transform(normalize_middle_name, field="middle_name", priority=0)
    # registry.register_column_validator(validate_middle_name, field="middle_name", priority=0)


def detect_middle_name_header_common_names(
    *,
    table: pl.DataFrame,  # Extracted table (pre-mapping; header row already applied)
    column: pl.Series,  # Current column as a Series
    column_sample_non_empty_values: list[str],  # Trimmed, non-empty sample from this column (strings)
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

    raw = (column_header_original or "").strip().lower()
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
    column_sample_non_empty_values: list[str],  # Trimmed, non-empty sample from this column (strings)
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
      - Recognize columns that are mostly initials: "A" or "A."
    """
    if not column_sample_non_empty_values:
        return None

    matches = 0
    total = 0
    for s in column_sample_non_empty_values:
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
    settings: Settings,  # Engine Settings
    metadata: Mapping[str, Any],  # Run metadata
    state: MutableMapping[str, Any],  # Mutable dict shared across the run
    logger: RunLogger,  # RunLogger (structured events + text logs)
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
    settings: Settings,  # Engine Settings
    metadata: Mapping[str, Any],  # Run metadata
    state: MutableMapping[str, Any],  # Mutable dict shared across the run
    logger: RunLogger,  # RunLogger (structured events + text logs)
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
