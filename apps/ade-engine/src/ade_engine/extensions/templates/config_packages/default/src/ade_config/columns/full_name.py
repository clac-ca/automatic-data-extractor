from __future__ import annotations

import re

import polars as pl

from ade_engine.models import FieldDef

# Teaching note:
# These patterns are intentionally simple. They are for *detection and normalization* examples.
COMMA_NAME_RE = re.compile(r"^[A-Za-z][\w'\-]*,\s*[A-Za-z][\w'\-]*$")
SPACE_NAME_RE = re.compile(r"^[A-Za-z][\w'\-]*\s+[A-Za-z][\w'\-]*$")

# Allowed characters for validation (letters + spaces + hyphen + apostrophe).
ALLOWED_FULL_NAME_PATTERN = r"^[A-Za-z][A-Za-z '\-]*$"


def register(registry):
    registry.register_field(FieldDef(name="full_name", label="Full Name", dtype="string"))
    registry.register_column_detector(detect_full_name_header, field="full_name", priority=30)
    registry.register_column_detector(detect_full_name_values, field="full_name", priority=10)
    registry.register_column_transform(split_full_name, field="full_name", priority=0)
    registry.register_column_validator(validate_full_name, field="full_name", priority=0)


def detect_full_name_header(
    *,
    table: pl.DataFrame,
    column: pl.Series,
    column_sample: list[str],
    column_name: str,
    column_index: int,
    header_text: str,
    settings,
    sheet_name: str,
    metadata: dict,
    state: dict,
    input_file_name: str | None,
    logger,
) -> dict[str, float] | None:
    """Header-based detection: exact matches are high confidence."""
    header = (header_text or "").strip().lower()
    if header == "full name":
        return {"full_name": 1.0}
    if header == "name":
        return {"full_name": 0.8}
    return None


def detect_full_name_values(
    *,
    table: pl.DataFrame,
    column: pl.Series,
    column_sample: list[str],
    column_name: str,
    column_index: int,
    header_text: str,
    settings,
    sheet_name: str,
    metadata: dict,
    state: dict,
    input_file_name: str | None,
    logger,
) -> dict[str, float] | None:
    """Value-based detection using the sample.

    Heuristic:
    - "Last, First" OR "First Last"
    - skip values that contain digits (often IDs/codes)
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

    score = matches / total
    return {"full_name": float(score)}


def split_full_name(
    *,
    field_name: str,
    table: pl.DataFrame,
    settings,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger,
) -> dict[str, pl.Expr]:
    """Normalize `full_name` and emit derived `first_name` / `last_name`.

    Teaching notes:
    - A transform may return a dict[str, pl.Expr] to populate multiple columns.
    - This example **does not overwrite** existing first/last name values when present.
    """
    full = pl.col(field_name).cast(pl.Utf8).str.strip_chars()

    # Normalize whitespace and empty values.
    full = full.str.replace_all(r"\s+", " ")
    full = pl.when(full.is_null() | (full == "")).then(pl.lit(None)).otherwise(full)

    has_comma = full.str.contains(",")
    has_space = full.str.contains(r"\s")

    comma_parts = full.str.split(",")
    comma_last = comma_parts.list.first().cast(pl.Utf8).str.strip_chars()
    comma_first = comma_parts.list.last().cast(pl.Utf8).str.strip_chars()

    space_parts = full.str.split(" ")
    space_first = space_parts.list.first().cast(pl.Utf8).str.strip_chars()
    space_last = space_parts.list.last().cast(pl.Utf8).str.strip_chars()

    derived_first = pl.when(has_comma).then(comma_first).otherwise(space_first)
    derived_last = pl.when(has_comma).then(comma_last).otherwise(space_last)

    derived_first = pl.when(derived_first.is_null() | (derived_first == "")).then(pl.lit(None)).otherwise(derived_first)
    derived_last = pl.when(derived_last.is_null() | (derived_last == "")).then(pl.lit(None)).otherwise(derived_last)

    # Only rebuild the full name when we actually had evidence of multiple parts.
    can_rebuild = (has_comma | has_space) & derived_first.is_not_null() & derived_last.is_not_null()
    normalized_full = (
        pl.when(can_rebuild)
        .then(pl.concat_str([derived_first, derived_last], separator=" "))
        .otherwise(full)
    )

    # Preserve existing first/last if already populated (do not overwrite with derived values).
    if "first_name" in table.columns:
        existing_first = pl.col("first_name").cast(pl.Utf8).str.strip_chars()
        existing_first = pl.when(existing_first.is_null() | (existing_first == "")).then(pl.lit(None)).otherwise(
            existing_first
        )
        first_out = pl.coalesce([existing_first, derived_first])
    else:
        first_out = derived_first

    if "last_name" in table.columns:
        existing_last = pl.col("last_name").cast(pl.Utf8).str.strip_chars()
        existing_last = pl.when(existing_last.is_null() | (existing_last == "")).then(pl.lit(None)).otherwise(
            existing_last
        )
        last_out = pl.coalesce([existing_last, derived_last])
    else:
        last_out = derived_last

    return {
        "full_name": normalized_full,
        "first_name": first_out,
        "last_name": last_out,
    }


def validate_full_name(
    *,
    field_name: str,
    table: pl.DataFrame,
    settings,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger,
) -> pl.Expr:
    """Validate allowed characters + show a simple cross-field rule."""
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()

    format_issue = (
        pl.when(v.is_not_null() & (v != "") & ~v.str.contains(ALLOWED_FULL_NAME_PATTERN))
        .then(pl.lit("Full name must be letters with spaces/hyphens/apostrophes"))
        .otherwise(pl.lit(None))
    )

    # Cross-field check (post-mapping):
    # If first+last exist but full_name is missing, emit an issue.
    if "first_name" in table.columns and "last_name" in table.columns:
        first = pl.col("first_name").cast(pl.Utf8).str.strip_chars()
        last = pl.col("last_name").cast(pl.Utf8).str.strip_chars()

        missing_full = v.is_null() | (v == "")
        parts_present = first.is_not_null() & (first != "") & last.is_not_null() & (last != "")

        parts_issue = (
            pl.when(missing_full & parts_present)
            .then(pl.lit("Full name missing but first/last are present"))
            .otherwise(pl.lit(None))
        )

        return pl.coalesce([format_issue, parts_issue])

    return format_issue
