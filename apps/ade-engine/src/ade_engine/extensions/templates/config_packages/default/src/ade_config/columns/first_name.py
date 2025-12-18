from __future__ import annotations

import polars as pl

from ade_engine.models import FieldDef


def register(registry):
    registry.register_field(FieldDef(name="first_name", label="First Name", dtype="string"))
    registry.register_column_detector(detect_first_name_header, field="first_name", priority=50)
    registry.register_column_detector(detect_first_name_values, field="first_name", priority=20)
    registry.register_column_transform(normalize_first_name, field="first_name", priority=0)
    registry.register_column_validator(validate_first_name, field="first_name", priority=0)


def detect_first_name_header(
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
    """Header-based detection for first_name."""
    tokens = set((header_text or "").lower().replace("-", " ").split())
    if not tokens:
        return None

    if "first" in tokens and "name" in tokens:
        return {"first_name": 1.0}
    if "fname" in tokens or "given" in tokens:
        return {"first_name": 0.9}

    return None


def detect_first_name_values(
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
    """Value-based detection + (optional) neighbor boost.

    Teaching notes:
    - During detection, canonical field names are not known.
    - If you need cross-column evidence, use `column_index` and look at neighbors by position.
    """
    if not column_sample:
        return None

    def looks_like_first_token(s: str) -> bool:
        # Simple, readable heuristic for a template:
        # - no digits
        # - no spaces
        # - reasonable length
        if any(ch.isdigit() for ch in s):
            return False
        if " " in s:
            return False
        return 2 <= len(s) <= 20

    good = sum(1 for s in column_sample if looks_like_first_token(s))
    score = good / len(column_sample)

    # Optional boost: if the right neighbor also looks like a name column,
    # increase confidence (common layout: First Name | Last Name).
    if column_index + 1 < len(table.columns):
        row_n = settings.detectors.row_sample_size
        text_n = settings.detectors.text_sample_size

        t = table.head(row_n)
        right_col_name = t.columns[column_index + 1]

        right_series = t.get_column(right_col_name).cast(pl.Utf8).str.strip_chars()
        right_series = right_series.drop_nulls()
        right_series = right_series.filter(right_series != "")
        right_sample = right_series.head(text_n).to_list()

        if right_sample:
            right_good = sum(1 for s in right_sample if looks_like_first_token(s))
            right_score = right_good / len(right_sample)

            if score >= 0.7 and right_score >= 0.7:
                score = min(1.0, score + 0.15)

    return {"first_name": float(score)}


def normalize_first_name(
    *,
    field_name: str,
    table: pl.DataFrame,
    settings,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger,
) -> pl.Expr:
    """Trim and convert empty -> null."""
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()
    return pl.when(v.is_null() | (v == "")).then(pl.lit(None)).otherwise(v)


def validate_first_name(
    *,
    field_name: str,
    table: pl.DataFrame,
    settings,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger,
) -> pl.Expr:
    """Example validation: keep it straightforward."""
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()

    return (
        pl.when(v.is_not_null() & (v != "") & (v.str.len_chars() > 50))
        .then(pl.lit("First name too long"))
        .otherwise(pl.lit(None))
    )
