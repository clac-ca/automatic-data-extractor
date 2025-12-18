from __future__ import annotations

import polars as pl

from ade_engine.models import FieldDef

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def register(registry):
    registry.register_field(FieldDef(name="email", dtype="string"))
    registry.register_column_detector(detect_email_header, field="email", priority=60)
    registry.register_column_detector(detect_email_values, field="email", priority=30)
    registry.register_column_transform(normalize_email, field="email", priority=0)
    registry.register_column_validator(validate_email, field="email", priority=0)


def detect_email_header(
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
    header = (header_text or "").strip().lower()
    if not header:
        return None
    if "email" in header or "e-mail" in header:
        return {"email": 1.0}
    return None


def detect_email_values(
    *,
    table: pl.DataFrame,  # Table DF (pre-mapping; extracted headers, data rows only)
    column: pl.Series,  # Current column Series (same as table.get_column(column_name))
    column_sample: list[str],  # Trimmed, non-empty string sample from this column
    column_name: str,  # Current DF column name (extracted header; not canonical)
    column_index: int,
    header_text: str,  # Trimmed header cell text for this column ("" if missing)
    settings,  # Engine Settings (use settings.detectors.* for sampling)
    sheet_name: str,  # Worksheet title
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Value-based detection using Polars (no Python loops).

    Note: During detection, do NOT rely on semantic column names. We reference the
    current column via ``column_index``.
    """

    row_n = settings.detectors.row_sample_size
    text_n = settings.detectors.text_sample_size

    t = table.head(row_n)
    col_name = t.columns[column_index]

    text = pl.col(col_name).cast(pl.Utf8).str.strip_chars().str.to_lowercase()

    # Keep only non-empty values and cap.
    t = t.filter(text.is_not_null() & (text != "")).head(text_n)
    if t.height == 0:
        return None

    score = t.select(text.str.contains(EMAIL_PATTERN).mean().alias("score")).to_series(0)[0]
    if score is None:
        return None
    return {"email": float(score)}


def normalize_email(
    *,
    field_name: str,  # Canonical field name being transformed (post-mapping)
    table: pl.DataFrame,  # Current table DF (post-mapping)
    settings,  # Engine Settings
    state: dict,  # Mutable dict shared across the run
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> pl.Expr:
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars().str.to_lowercase()
    return pl.when(v.is_null() | (v == "")).then(pl.lit(None)).otherwise(v)


def validate_email(
    *,
    field_name: str,  # Canonical field name being validated (post-mapping)
    table: pl.DataFrame,  # Current table DF (post-mapping)
    settings,  # Engine Settings
    state: dict,  # Mutable dict shared across the run
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> pl.Expr:
    v = pl.col(field_name).cast(pl.Utf8).str.strip_chars().str.to_lowercase()

    format_issue = (
        pl.when(v.is_not_null() & (v != "") & ~v.str.contains(EMAIL_PATTERN))
        .then(pl.format("Invalid email: {}", v))
        .otherwise(pl.lit(None))
    )

    # Example cross-field rule (optional):
    # If a row has an email but no name fields, flag it (only if those columns exist).
    if "first_name" in table.columns and "last_name" in table.columns:
        first = pl.col("first_name").cast(pl.Utf8).str.strip_chars()
        last = pl.col("last_name").cast(pl.Utf8).str.strip_chars()

        missing_name = (
            v.is_not_null()
            & (v != "")
            & (first.is_null() | (first == ""))
            & (last.is_null() | (last == ""))
        )

        name_issue = (
            pl.when(missing_name)
            .then(pl.lit("Email present but first/last name are missing"))
            .otherwise(pl.lit(None))
        )

        # Prefer format issues; otherwise emit the cross-field issue.
        return pl.coalesce([format_issue, name_issue])

    return format_issue
