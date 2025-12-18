from __future__ import annotations

import re

import polars as pl

from ade_engine.models import FieldDef

FIELD_NAME = "middle_name"

_HEADER_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

HEADER_TOKEN_SETS_STRONG: list[set[str]] = [
    {"middle", "name"},
    {"middlename"},
    {"middle", "initial"},
    {"middleinitial"},
    {"mi"},
    {"m", "i"},  # supports "M.I." -> "m i"
]


def register(registry):
    registry.register_field(FieldDef(name=FIELD_NAME, label="Middle Name", dtype="string"))

    # Enabled by default:
    registry.register_column_detector(detect_middle_name_header_common_names, field=FIELD_NAME, priority=60)

    # Examples (uncomment to enable)
    # -------------------------------------------------
    # Example 1: value-based detection
    # Purpose: detect middle initial columns ("A" / "A.").
    # registry.register_column_detector(detect_middle_name_values_initials, field=FIELD_NAME, priority=30)

    # Example 2: normalization
    # Purpose: trim and convert empty -> null.
    # registry.register_column_transform(normalize_middle_name, field=FIELD_NAME, priority=0)

    # Example 3: validation
    # Purpose: flag unusually long values.
    # registry.register_column_validator(validate_middle_name, field=FIELD_NAME, priority=0)


def detect_middle_name_header_common_names(
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
      - Match typical middle-name headers ("middle name", "mi", "middle initial", ...).
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


def detect_middle_name_values_initials(
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

    return {FIELD_NAME: float(matches / total)}


def normalize_middle_name(
    *,
    field_name: str,
    table: pl.DataFrame,
    settings,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger,
) -> pl.Expr:
    """Example (disabled by default)."""
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()
    return pl.when(v.is_null() | (v == "")).then(pl.lit(None)).otherwise(v)


def validate_middle_name(
    *,
    field_name: str,
    table: pl.DataFrame,
    settings,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger,
) -> pl.Expr:
    """Example (disabled by default)."""
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()
    return (
        pl.when(v.is_not_null() & (v != "") & (v.str.len_chars() > 40))
        .then(pl.lit("Middle name is unusually long"))
        .otherwise(pl.lit(None))
    )
