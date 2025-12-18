from __future__ import annotations

import polars as pl

from ade_engine.models import FieldDef


def register(registry):
    registry.register_field(FieldDef(name="last_name", label="Last Name", dtype="string"))
    registry.register_column_detector(detect_last_name_header, field="last_name", priority=50)
    registry.register_column_detector(detect_last_name_values, field="last_name", priority=20)
    registry.register_column_transform(normalize_last_name, field="last_name", priority=0)
    registry.register_column_validator(validate_last_name, field="last_name", priority=0)


def detect_last_name_header(
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
    """Header-based detection for last_name."""
    tokens = set((header_text or "").lower().replace("-", " ").split())
    if not tokens:
        return None

    if ("last" in tokens and "name" in tokens) or "surname" in tokens or "family" in tokens:
        return {"last_name": 1.0}
    if "lname" in tokens:
        return {"last_name": 0.9}

    return None


def detect_last_name_values(
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
    """Value-based detection + (optional) neighbor boost (left neighbor).

    This mirrors the first_name example, but checks the left neighbor to show both directions.
    """
    if not column_sample:
        return None

    def looks_like_last_token(s: str) -> bool:
        if any(ch.isdigit() for ch in s):
            return False
        if " " in s:
            return False
        return len(s) >= 2

    good = sum(1 for s in column_sample if looks_like_last_token(s))
    score = good / len(column_sample)

    # Optional boost: if the left neighbor is also name-like, increase confidence.
    if column_index - 1 >= 0:
        row_n = settings.detectors.row_sample_size
        text_n = settings.detectors.text_sample_size

        t = table.head(row_n)
        left_col_name = t.columns[column_index - 1]

        left_series = t.get_column(left_col_name).cast(pl.Utf8).str.strip_chars()
        left_series = left_series.drop_nulls()
        left_series = left_series.filter(left_series != "")
        left_sample = left_series.head(text_n).to_list()

        if left_sample:
            left_good = sum(1 for s in left_sample if 2 <= len(s) <= 20 and " " not in s and not any(ch.isdigit() for ch in s))
            left_score = left_good / len(left_sample)

            if score >= 0.7 and left_score >= 0.7:
                score = min(1.0, score + 0.15)

    return {"last_name": float(score)}


def normalize_last_name(
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


def validate_last_name(
    *,
    field_name: str,
    table: pl.DataFrame,
    settings,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger,
) -> pl.Expr:
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()

    return (
        pl.when(v.is_not_null() & (v != "") & (v.str.len_chars() > 80))
        .then(pl.lit("Last name too long"))
        .otherwise(pl.lit(None))
    )
