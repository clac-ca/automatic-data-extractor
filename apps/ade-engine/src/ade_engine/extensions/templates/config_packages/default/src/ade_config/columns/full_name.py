from __future__ import annotations

import re

import polars as pl

from ade_engine.models import FieldDef

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


def register(registry):
    registry.register_field(FieldDef(name=FIELD_NAME, label="Full Name", dtype="string"))

    # Enabled by default:
    registry.register_column_detector(detect_full_name_header_common_names, field=FIELD_NAME, priority=60)

    # Examples (uncomment to enable)
    # -------------------------------------------------
    # Example 1: value-based detection
    # Purpose: detect full-name columns even when headers are blank / unhelpful.
    # registry.register_column_detector(detect_full_name_values_basic, field=FIELD_NAME, priority=30)

    # Example 2: transform that populates multiple fields
    # Purpose: split full_name into first_name / last_name without overwriting existing values.
    # registry.register_column_transform(split_full_name, field=FIELD_NAME, priority=0)

    # Example 3: validation
    # Purpose: flag unexpected characters and a simple cross-field consistency issue.
    # registry.register_column_validator(validate_full_name, field=FIELD_NAME, priority=0)


def detect_full_name_header_common_names(
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
    """Example (disabled by default).

    Purpose:
      - Demonstrate a transform that returns multiple columns.
      - Split "full_name" into "first_name" and "last_name".
      - Do NOT overwrite first/last if they already have values.
    """
    full = pl.col(field_name).cast(pl.Utf8).str.strip_chars()
    full = full.str.replace_all(r"\s+", " ")
    full = pl.when(full.is_null() | (full == "")).then(pl.lit(None)).otherwise(full)

    has_comma = full.str.contains(",")

    comma_parts = full.str.split(",")
    comma_last = comma_parts.list.get(0).cast(pl.Utf8).str.strip_chars()
    comma_first = comma_parts.list.get(1).cast(pl.Utf8).str.strip_chars()

    space_parts = full.str.split(" ")
    space_first = space_parts.list.get(0).cast(pl.Utf8).str.strip_chars()
    space_last = space_parts.list.get(-1).cast(pl.Utf8).str.strip_chars()

    derived_first = pl.when(has_comma).then(comma_first).otherwise(space_first)
    derived_last = pl.when(has_comma).then(comma_last).otherwise(space_last)

    derived_first = pl.when(derived_first.is_null() | (derived_first == "")).then(pl.lit(None)).otherwise(derived_first)
    derived_last = pl.when(derived_last.is_null() | (derived_last == "")).then(pl.lit(None)).otherwise(derived_last)

    normalized_full = (
        pl.when(derived_first.is_not_null() & derived_last.is_not_null())
        .then(pl.concat_str([derived_first, derived_last], separator=" "))
        .otherwise(full)
    )

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
    """Example (disabled by default).

    Purpose:
      - Flag unexpected characters.
      - Show a simple cross-field consistency check (if first+last exist but full is missing).
    """
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()

    format_issue = (
        pl.when(v.is_not_null() & (v != "") & ~v.str.contains(ALLOWED_FULL_NAME_PATTERN))
        .then(pl.lit("Full name contains unexpected characters"))
        .otherwise(pl.lit(None))
    )

    if "first_name" in table.columns and "last_name" in table.columns:
        first = pl.col("first_name").cast(pl.Utf8).str.strip_chars()
        last = pl.col("last_name").cast(pl.Utf8).str.strip_chars()

        missing_full = v.is_null() | (v == "")
        parts_present = first.is_not_null() & (first != "") & last.is_not_null() & (last != "")

        parts_issue = (
            pl.when(missing_full & parts_present)
            .then(pl.lit("Full name is missing but first/last are present"))
            .otherwise(pl.lit(None))
        )

        return pl.coalesce([format_issue, parts_issue])

    return format_issue
