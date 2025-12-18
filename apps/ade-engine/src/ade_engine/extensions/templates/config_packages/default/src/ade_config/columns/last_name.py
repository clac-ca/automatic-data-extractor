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
    t = set((header_text or "").lower().replace("-", " ").split())
    if not t:
        return None
    if ("last" in t and "name" in t) or "surname" in t or "family" in t:
        return {"last_name": 1.0}
    if "lname" in t:
        return {"last_name": 0.9}
    return None


def detect_last_name_values(
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
    row_n = settings.detectors.row_sample_size
    text_n = settings.detectors.text_sample_size

    t = table.head(row_n)
    col_name = t.columns[column_index]

    text = pl.col(col_name).cast(pl.Utf8).str.strip_chars()
    t0 = t.filter(text.is_not_null() & (text != "")).head(text_n)
    if t0.height == 0:
        return None

    single_token = ~text.str.contains(r"\s")
    length_ok = text.str.len_chars() >= 2
    score = t0.select((single_token & length_ok).mean().alias("score")).to_series(0)[0]
    if score is None:
        return None
    return {"last_name": float(score)}


def normalize_last_name(
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

    if "full_name" not in table.columns:
        return v

    full = pl.col("full_name").cast(pl.Utf8).str.strip_chars()
    from_full = full.str.split(" ").list.get(-1, null_on_oob=True).cast(pl.Utf8).str.strip_chars()

    return pl.when(v.is_null() & full.is_not_null() & (full != "")).then(from_full).otherwise(v)


def validate_last_name(
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
        pl.when(v.is_not_null() & (v != "") & (v.str.len_chars() > 80))
        .then(pl.lit("Last name too long"))
        .otherwise(pl.lit(None))
    )
