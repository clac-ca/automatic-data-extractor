from __future__ import annotations

import polars as pl


def register(registry):
    registry.register_hook(on_table_transformed, hook="on_table_transformed", priority=0)

    # Examples (uncomment to enable)
    # registry.register_hook(on_table_transformed_example_1_trim_text_and_null_empty, hook="on_table_transformed", priority=0)
    # registry.register_hook(on_table_transformed_example_2_ensure_full_name_column, hook="on_table_transformed", priority=0)
    # registry.register_hook(on_table_transformed_example_3_backfill_full_name, hook="on_table_transformed", priority=0)
    # registry.register_hook(on_table_transformed_example_4_parse_amount_currency, hook="on_table_transformed", priority=0)
    # registry.register_hook(on_table_transformed_example_5_drop_all_null_rows, hook="on_table_transformed", priority=0)


def on_table_transformed(
    *,
    hook_name,  # HookName enum value for this stage
    settings,  # Engine Settings
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    workbook,  # None for this stage (table hooks run before output workbook exists)
    sheet,  # Source worksheet (openpyxl Worksheet)
    table: pl.DataFrame,  # Current table DF (post-transforms; pre-validation)
    write_table,  # None for this stage
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> pl.DataFrame | None:
    """Post-transform hook (pre-validation).

    This hook is called once per detected table *after*:

    - header/region detection
    - mapping (source headers -> canonical field names)
    - registered column transforms (value normalization)

    and *before* validators run. The DataFrame returned from this hook (if any)
    is what validation sees next.

    Use this hook for table-level adjustments that are awkward to express as
    per-field transforms, such as:

    - cross-column fixes (derive one column from others, swap/repair related values)
    - type coercion / parsing (dates, currency) to prepare for validators
    - adding missing required columns (so downstream validators can run)
    - dropping obviously-non-data rows (blank lines, repeated headers, footers)

    If you want to filter based on validation results (e.g., drop rows that have
    issues), do that in `on_table_validated` instead.

    Return a new DataFrame to replace ``table`` (or return None to keep it).
    """

    if logger:
        logger.info("Config hook: table transformed (columns=%s)", list(table.columns))

    return None


def on_table_transformed_example_1_trim_text_and_null_empty(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame:
    """Example: trim whitespace and convert empty strings to nulls for all text columns."""

    return table.with_columns(pl.col(pl.Utf8).str.strip_chars().replace("", None))


def on_table_transformed_example_2_ensure_full_name_column(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame | None:
    """Example: ensure a column exists before validation (useful for optional inputs)."""

    if "full_name" not in table.columns:
        return table.with_columns(pl.lit(None).cast(pl.Utf8).alias("full_name"))
    return None


def on_table_transformed_example_3_backfill_full_name(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame | None:
    """Example: backfill `full_name` from `first_name` + `last_name` when missing."""

    if {"first_name", "last_name", "full_name"}.issubset(table.columns):
        first = pl.col("first_name").cast(pl.Utf8).str.strip_chars().replace("", None)
        last = pl.col("last_name").cast(pl.Utf8).str.strip_chars().replace("", None)
        full = pl.col("full_name").cast(pl.Utf8).str.strip_chars().replace("", None)
        return table.with_columns(
            pl.when(full.is_null() & first.is_not_null() & last.is_not_null())
            .then(pl.concat_str([first, last], separator=" "))
            .otherwise(full)
            .alias("full_name")
        )
    return None


def on_table_transformed_example_4_parse_amount_currency(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame | None:
    """Example: parse a currency-like string column into Float64."""

    if "amount" in table.columns:
        return table.with_columns(
            pl.col("amount")
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.replace_all(r"[,$]", "")
            .cast(pl.Float64, strict=False)
            .alias("amount")
        )
    return None


def on_table_transformed_example_5_drop_all_null_rows(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame:
    """Example: drop rows that are completely empty (all columns null)."""

    return table.filter(pl.any_horizontal(pl.all().is_not_null()))
