from __future__ import annotations

import polars as pl


# -----------------------------------------------------------------------------
# Hook: `on_table_mapped`
#
# When is this called?
# - Once per detected table region, after column mapping has been applied and
#   before any transforms/validators run.
# - Mapping is rename-only: the engine renames extracted columns to canonical
#   field names where confident; unmapped columns remain in the same DataFrame.
#
# What is this hook good for?
# - Table-level cleanup before transforms (drop blank rows, trim whitespace,
#   normalize common null/sentinel values like "N/A")
# - Combining/splitting columns when the logic involves multiple fields
# - Recording per-run facts in `state` for later hooks (counts, flags, etc.)
#
# Return value:
# - Return a new `pl.DataFrame` to replace `table` for the rest of the pipeline,
#   or return `None` to keep the current table unchanged.
# -----------------------------------------------------------------------------
def register(registry):
    registry.register_hook(on_table_mapped, hook="on_table_mapped", priority=0)

    # Examples (uncomment to enable)
    # registry.register_hook(on_table_mapped_example_1_trim_all_string_columns, hook="on_table_mapped", priority=0)
    # registry.register_hook(on_table_mapped_example_2_normalize_empty_sentinels, hook="on_table_mapped", priority=0)
    # registry.register_hook(on_table_mapped_example_3_drop_fully_empty_rows, hook="on_table_mapped", priority=0)
    # registry.register_hook(on_table_mapped_example_4_derive_full_name, hook="on_table_mapped", priority=0)
    # registry.register_hook(on_table_mapped_example_5_record_tables_seen, hook="on_table_mapped", priority=0)


def on_table_mapped(
    *,
    hook_name,  # HookName enum value for this stage
    settings,  # Engine Settings
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    workbook,  # None for this stage (table hooks run before output workbook exists)
    sheet,  # Source worksheet (openpyxl Worksheet)
    table: pl.DataFrame,
    write_table,  # None for this stage
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> pl.DataFrame | None:
    """Post-mapping hook (mapping is rename-only; pre-transform)."""

    if logger:
        logger.info("Config hook: table mapped (columns=%s)", list(table.columns))

    return None


def on_table_mapped_example_1_trim_all_string_columns(
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
    """Example: trim all string columns (safe, cheap, and often useful)."""

    return table.with_columns(pl.col(pl.Utf8).str.strip_chars())


def on_table_mapped_example_2_normalize_empty_sentinels(
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
    """Example: normalize common "empty" sentinels to null (across all string columns)."""

    empty_tokens = ["", "n/a", "na", "null", "none", "-"]
    trimmed = pl.col(pl.Utf8).str.strip_chars()
    return table.with_columns(
        pl.when(trimmed.str.to_lowercase().is_in(empty_tokens))
        .then(None)
        .otherwise(trimmed)
        .name.keep()
    )


def on_table_mapped_example_3_drop_fully_empty_rows(
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
    """Example: drop rows that are entirely empty (all values null/blank after trimming)."""

    non_empty_row = pl.any_horizontal(
        [
            pl.col(c).is_not_null() & (pl.col(c).cast(pl.Utf8).str.strip_chars() != "")
            for c in table.columns
        ]
    )
    return table.filter(non_empty_row)


def on_table_mapped_example_4_derive_full_name(
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
    """Example: create a derived `full_name` column from `first_name` + `last_name`."""

    if {"first_name", "last_name"} <= set(table.columns):
        return table.with_columns(
            pl.concat_str(
                [
                    pl.col("first_name").cast(pl.Utf8).fill_null("").str.strip_chars(),
                    pl.col("last_name").cast(pl.Utf8).fill_null("").str.strip_chars(),
                ],
                separator=" ",
            )
            .str.strip_chars()
            .alias("full_name")
        )
    return None


def on_table_mapped_example_5_record_tables_seen(
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
) -> None:
    """Example: record per-run facts in shared state for later hooks."""

    state["tables_seen"] = int(state.get("tables_seen", 0)) + 1
