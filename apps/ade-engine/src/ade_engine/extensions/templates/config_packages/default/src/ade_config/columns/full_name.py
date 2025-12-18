from __future__ import annotations

import polars as pl

from ade_engine.models import FieldDef

COMMA_NAME_PATTERN = r"^[A-Za-z][\w'\-]*,\s*[A-Za-z][\w'\-]*$"
SPACE_NAME_PATTERN = r"^[A-Za-z][\w'\-]*\s+[A-Za-z][\w'\-]*$"
ALLOWED_FULL_NAME_PATTERN = r"^[A-Za-z][A-Za-z '-]*$"


def register(registry):
    registry.register_field(FieldDef(name="full_name", label="Full Name", dtype="string"))
    registry.register_column_detector(detect_full_name_header, field="full_name", priority=30)
    registry.register_column_detector(detect_full_name_values, field="full_name", priority=10)
    registry.register_column_transform(split_full_name, field="full_name", priority=0)
    registry.register_column_validator(validate_full_name, field="full_name", priority=0)


def detect_full_name_header(
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
    """Real-world but simple: exact "full name" boosts, also slightly nudges plain "name"."""

    header = (header_text or "").strip().lower()
    if header == "full name":
        return {"full_name": 1.0}
    if header == "name":
        return {"full_name": 0.8}
    return None


def detect_full_name_values(
    *,
    table: pl.DataFrame,
    column: pl.Series,  # Current column Series (same as table.get_column(column_name))
    column_sample: list[str],  # Trimmed, non-empty string sample from this column
    column_name: str,  # Current DF column name (extracted header; not canonical)
    column_index: int,
    settings,
    header_text: str,  # Trimmed header cell text for this column ("" if missing)
    sheet_name: str,  # Worksheet title
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> dict[str, float] | None:
    """Look for "Last, First" or "First Last" patterns (Polars-first; no loops)."""

    row_n = settings.detectors.row_sample_size
    text_n = settings.detectors.text_sample_size

    t = table.head(row_n)
    col_name = t.columns[column_index]
    text = pl.col(col_name).cast(pl.Utf8).str.strip_chars()

    # Ignore empty and digit-containing strings (often IDs/codes).
    t0 = t.filter(text.is_not_null() & (text != "") & ~text.str.contains(r"\d")).head(text_n)
    if t0.height == 0:
        return None

    is_comma = text.str.contains(COMMA_NAME_PATTERN)
    is_space = text.str.contains(SPACE_NAME_PATTERN)

    score = t0.select((is_comma | is_space).mean().alias("score")).to_series(0)[0]
    if score is None:
        return None
    return {"full_name": float(score)}


def split_full_name(
    *,
    field_name: str,  # Canonical field name being transformed (post-mapping)
    table: pl.DataFrame,  # Current table DF (post-mapping)
    settings,  # Engine Settings
    state: dict,  # Mutable dict shared across the run
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> dict[str, pl.Expr]:
    """Normalize full_name and emit derived first_name / last_name expressions."""

    full = pl.col(field_name).cast(pl.Utf8).str.strip_chars()
    full = pl.when(full.is_null() | (full == "")).then(pl.lit(None)).otherwise(full)
    comma = full.str.contains(",")

    comma_parts = full.str.split(",")
    comma_last = comma_parts.list.get(0, null_on_oob=True).cast(pl.Utf8).str.strip_chars()
    comma_first = comma_parts.list.get(1, null_on_oob=True).cast(pl.Utf8).str.strip_chars()

    space_parts = full.str.split(" ")
    space_first = space_parts.list.get(0, null_on_oob=True).cast(pl.Utf8).str.strip_chars()
    space_last = space_parts.list.get(-1, null_on_oob=True).cast(pl.Utf8).str.strip_chars()

    from_full_first = pl.when(comma).then(comma_first).otherwise(space_first)
    from_full_last = pl.when(comma).then(comma_last).otherwise(space_last)

    # Important: this transform may run even when the input file had no full_name
    # column (the engine creates missing canonical fields as null). Avoid
    # overwriting mapped first/last name columns with nulls in that case.
    if "first_name" in table.columns:
        existing = pl.col("first_name").cast(pl.Utf8).str.strip_chars()
        existing = pl.when(existing.is_null() | (existing == "")).then(pl.lit(None)).otherwise(existing)
        first_name = pl.when(existing.is_null()).then(from_full_first).otherwise(existing)
    else:
        first_name = from_full_first

    if "last_name" in table.columns:
        existing = pl.col("last_name").cast(pl.Utf8).str.strip_chars()
        existing = pl.when(existing.is_null() | (existing == "")).then(pl.lit(None)).otherwise(existing)
        last_name = pl.when(existing.is_null()).then(from_full_last).otherwise(existing)
    else:
        last_name = from_full_last

    normalized_from_full = pl.when(from_full_first.is_not_null() & from_full_last.is_not_null()).then(
        pl.concat_str([from_full_first, from_full_last], separator=" ")
    ).otherwise(full)

    # If full_name is empty but parts exist, backfill it from first/last.
    parts_present = first_name.is_not_null() & last_name.is_not_null()
    from_parts = pl.when(parts_present).then(pl.concat_str([first_name, last_name], separator=" ")).otherwise(
        pl.lit(None)
    )
    normalized_full = pl.when(full.is_not_null()).then(normalized_from_full).otherwise(from_parts)

    return {
        "full_name": normalized_full,
        "first_name": first_name,
        "last_name": last_name,
    }


def validate_full_name(
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

    format_issue = (
        pl.when(v.is_not_null() & (v != "") & ~v.str.contains(ALLOWED_FULL_NAME_PATTERN))
        .then(pl.lit("Full name must be letters with spaces/hyphens/apostrophes"))
        .otherwise(pl.lit(None))
    )

    # Cross-column validation (post-mapping): if first/last exist but full_name is
    # empty, flag it.
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
