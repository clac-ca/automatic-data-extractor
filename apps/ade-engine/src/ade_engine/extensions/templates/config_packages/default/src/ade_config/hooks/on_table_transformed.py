from __future__ import annotations

import polars as pl


def register(registry):
    registry.register_hook(on_table_transformed, hook="on_table_transformed", priority=0)


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

    # --- Examples (uncomment and adapt) ---------------------------------

    # Example: trim whitespace and convert empty strings to nulls for all text columns.
    # table = table.with_columns(pl.col(pl.Utf8).str.strip_chars().replace("", None))

    # Example: ensure a column exists before validation (useful for optional inputs).
    # if "full_name" not in table.columns:
    #     table = table.with_columns(pl.lit(None).cast(pl.Utf8).alias("full_name"))

    # Example: backfill `full_name` from `first_name` + `last_name` when missing.
    # if {"first_name", "last_name", "full_name"}.issubset(table.columns):
    #     first = pl.col("first_name").cast(pl.Utf8).str.strip_chars().replace("", None)
    #     last = pl.col("last_name").cast(pl.Utf8).str.strip_chars().replace("", None)
    #     full = pl.col("full_name").cast(pl.Utf8).str.strip_chars().replace("", None)
    #     table = table.with_columns(
    #         pl.when(full.is_null() & first.is_not_null() & last.is_not_null())
    #         .then(pl.concat_str([first, last], separator=" "))
    #         .otherwise(full)
    #         .alias("full_name")
    #     )

    # Example: parse a currency-like string column into Float64.
    # if "amount" in table.columns:
    #     table = table.with_columns(
    #         pl.col("amount")
    #         .cast(pl.Utf8)
    #         .str.strip_chars()
    #         .str.replace_all(r"[,$]", "")
    #         .cast(pl.Float64, strict=False)
    #         .alias("amount")
    #     )

    # Example: drop rows that are completely empty (all columns null).
    # table = table.filter(pl.any_horizontal(pl.all().is_not_null()))

    # If you uncomment any of the examples above, return the updated table by
    # replacing `return None` below with:
    # return table
    return None
