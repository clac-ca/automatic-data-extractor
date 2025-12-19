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
    """Register the `first_name` field and its detectors/transforms/validators."""
    registry.register_field(FieldDef(name="first_name", label="First Name", dtype="string"))
    registry.register_column_detector(detect_first_name_header_common_names, field="first_name", priority=60)

    # Examples (uncomment to enable)
    # registry.register_column_detector(detect_first_name_values_basic, field="first_name", priority=30)
    # registry.register_column_detector(detect_first_name_values_neighbor_pair, field="first_name", priority=25)
    # registry.register_column_transform(normalize_first_name, field="first_name", priority=0)
    # registry.register_column_validator(validate_first_name, field="first_name", priority=0)


def detect_first_name_header_common_names(
    *,
    table: pl.DataFrame,  # Extracted table (pre-mapping; header row already applied)
    column: pl.Series,  # Current column as a Series
    column_sample: list[str],  # Trimmed, non-empty sample from this column (strings)
    column_name: str,  # Extracted column name (not canonical yet)
    column_index: int,  # 0-based index in table.columns
    header_text: str,  # Header cell text ("" if missing)
    settings: Settings,  # Engine Settings
    sheet_name: str,  # Worksheet title
    table_region: TableRegion,  # Excel coords via .min_row/.max_row/.min_col/.max_col; helpers .a1/.header_row/.data_first_row
    table_index: int,  # 0-based index within the sheet (when multiple tables exist)
    metadata: Mapping[str, Any],  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: MutableMapping[str, Any],  # Mutable dict shared across the run
    input_file_name: str,  # Input filename (basename)
    logger: RunLogger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Enabled by default.

    Purpose:
      - Match typical first-name headers ("first name", "fname", "given name", ...).
    """
    header_non_alnum_re = re.compile(r"[^a-z0-9]+")
    header_token_sets_strong: list[set[str]] = [
        {"first", "name"},
        {"firstname"},
        {"fname"},
        {"given", "name"},
        {"givenname"},
        {"forename"},
    ]

    raw = (header_text or "").strip().lower()
    if not raw:
        return None

    normalized = header_non_alnum_re.sub(" ", raw).strip()
    tokens = set(normalized.split())
    if not tokens:
        return None

    if any(pattern <= tokens for pattern in header_token_sets_strong):
        return {"first_name": 1.0}

    return None


def detect_first_name_values_basic(
    *,
    table: pl.DataFrame,  # Extracted table (pre-mapping; header row already applied)
    column: pl.Series,  # Current column as a Series
    column_sample: list[str],  # Trimmed, non-empty sample from this column (strings)
    column_name: str,  # Extracted column name (not canonical yet)
    column_index: int,  # 0-based index in table.columns
    header_text: str,  # Header cell text ("" if missing)
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

    return {"first_name": float(good / total)}


def detect_first_name_values_neighbor_pair(
    *,
    table: pl.DataFrame,  # Extracted table (pre-mapping; header row already applied)
    column: pl.Series,  # Current column as a Series
    column_sample: list[str],  # Trimmed, non-empty sample from this column (strings)
    column_name: str,  # Extracted column name (not canonical yet)
    column_index: int,  # 0-based index in table.columns
    header_text: str,  # Header cell text ("" if missing)
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
        return {"first_name": float(base_score)}

    text_n = settings.detector_column_sample_size

    right_col_name = table.columns[column_index + 1]
    right_series = table.get_column(right_col_name)

    right_sample: list[str] = []
    for v in right_series:
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        right_sample.append(s)
        if len(right_sample) >= text_n:
            break

    if not right_sample:
        return {"first_name": float(base_score)}

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

    return {"first_name": score}


def normalize_first_name(
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
    settings: Settings,  # Engine Settings
    metadata: Mapping[str, Any],  # Run metadata
    state: MutableMapping[str, Any],  # Mutable dict shared across the run
    logger: RunLogger,  # RunLogger (structured events + text logs)
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
