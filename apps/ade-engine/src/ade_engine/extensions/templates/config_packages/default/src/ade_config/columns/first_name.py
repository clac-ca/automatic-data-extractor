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
    table: pl.DataFrame,  # Table DF (pre-mapping; extracted headers, data rows only)
    column: pl.Series,  # Current column Series (same as table.get_column(column_name))
    column_sample: list[str],  # Trimmed, non-empty string sample from this column
    column_name: str,  # Current DF column name (extracted header; not canonical)
    column_index: int,  # 0-based index of this column in table.columns
    header_text: str,
    settings,  # Engine Settings (use settings.detectors.* for sampling)
    sheet_name: str,  # Worksheet title
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    header_tokens = set((header_text or "").lower().replace("-", " ").split())
    if not header_tokens:
        return None
    if "first" in header_tokens and "name" in header_tokens:
        return {"first_name": 1.0}
    if "fname" in header_tokens or "given" in header_tokens:
        return {"first_name": 0.9}
    return None


def detect_first_name_values(
    *,
    table: pl.DataFrame,
    column: pl.Series,  # Current column Series (same as table.get_column(column_name))
    column_sample: list[str],  # Trimmed, non-empty string sample from this column
    column_name: str,  # Current DF column name (extracted header; not canonical)
    column_index: int,
    header_text: str,  # Trimmed header cell text for this column ("" if missing)
    settings,
    sheet_name: str,  # Worksheet title
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Name-like heuristic + cross-column boost.

    Notes:
    - During detection, do NOT rely on canonical field names existing in the table.
    - Cross-column heuristics should use ``column_index`` (neighbors by position).
    """

    row_n = settings.detectors.row_sample_size
    text_n = settings.detectors.text_sample_size

    t = table.head(row_n)
    col_name = t.columns[column_index]

    text = pl.col(col_name).cast(pl.Utf8).str.strip_chars()
    t0 = t.filter(text.is_not_null() & (text != "")).head(text_n)
    if t0.height == 0:
        return None

    single_token = ~text.str.contains(r"\s")
    length_ok = (text.str.len_chars() >= 2) & (text.str.len_chars() <= 20)
    score = t0.select((single_token & length_ok).mean().alias("score")).to_series(0)[0]
    if score is None:
        return None

    score_f = float(score)

    # Cross-column: if the right neighbor is also name-like, boost confidence
    # (common layout: First Name | Last Name).
    if column_index + 1 < len(t.columns):
        right_name = t.columns[column_index + 1]
        right_text = pl.col(right_name).cast(pl.Utf8).str.strip_chars()
        t1 = t.filter(right_text.is_not_null() & (right_text != "")).head(text_n)

        if t1.height > 0:
            right_single = ~right_text.str.contains(r"\s")
            right_len_ok = (right_text.str.len_chars() >= 2) & (right_text.str.len_chars() <= 20)
            right_score = t1.select((right_single & right_len_ok).mean().alias("score")).to_series(0)[0]
            if right_score is not None and float(right_score) >= 0.7 and score_f >= 0.7:
                score_f = min(1.0, score_f + 0.15)

    return {"first_name": score_f}


def normalize_first_name(
    *,
    field_name: str,  # Canonical field name being transformed (post-mapping)
    table: pl.DataFrame,  # Current table DF (post-mapping)
    settings,  # Engine Settings
    state: dict,  # Mutable dict shared across the run
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> pl.Expr:
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()
    v = pl.when(v.is_null() | (v == "")).then(pl.lit(None)).otherwise(v)

    # Demonstrates referencing another column in a transform (post-mapping), but
    # guarded so it only runs when the other field exists.
    if "full_name" not in table.columns:
        return v

    full = pl.col("full_name").cast(pl.Utf8).str.strip_chars()
    from_full = full.str.split(" ").list.get(0, null_on_oob=True).cast(pl.Utf8).str.strip_chars()

    return pl.when(v.is_null() & full.is_not_null() & (full != "")).then(from_full).otherwise(v)


def validate_first_name(
    *,
    field_name: str,  # Canonical field name being validated (post-mapping)
    table: pl.DataFrame,  # Current table DF (post-mapping)
    settings,  # Engine Settings
    state: dict,  # Mutable dict shared across the run
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> pl.Expr:
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars()
    return (
        pl.when(v.is_not_null() & (v != "") & (v.str.len_chars() > 50))
        .then(pl.lit("First name too long"))
        .otherwise(pl.lit(None))
    )
