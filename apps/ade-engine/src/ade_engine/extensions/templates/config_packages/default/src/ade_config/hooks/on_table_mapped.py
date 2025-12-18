"""ADE config hook: `on_table_mapped`

When this runs
--------------
- Once per detected table region, after column mapping and before transforms.
- Mapping is rename-only: extracted columns are renamed to canonical field names
  where confident; unmapped columns remain in the same DataFrame.

What it's useful for
--------------------
- Table-level cleanup (trim whitespace, normalize "empty" tokens, drop blank rows)
- Combining/splitting columns when the logic spans multiple fields
- Recording lightweight per-run facts in `state` for later hooks

Return value
------------
- Return a new `pl.DataFrame` to replace `table`, or return `None` to keep it unchanged.
- Returning anything else raises HookError.

Notes
-----
- `workbook` is `None` for this stage.
- ADE passes `table_region` (a `TableRegion`) describing the source header+data block in the
  input sheet using 1-based, inclusive (openpyxl-friendly) coordinates.
- `table_index` is a 0-based index within the sheet (useful when a sheet has multiple tables).
- Keep hooks deterministic + idempotent (re-running should yield the same output).
- Prefer vectorized Polars expressions; avoid Python row loops.

Template goals
--------------
- Default hook is safe and minimal (logs + lightweight counters).
- Examples are self-contained and opt-in (uncomment in `register()`).
"""

from __future__ import annotations

from typing import Any, MutableMapping, Sequence

import openpyxl
import openpyxl.worksheet.worksheet
import polars as pl

from ade_engine.models import TableRegion

# `TableRegion` (engine-owned, openpyxl-friendly coordinates):
# - header_row, first_col, last_row, last_col (1-based, inclusive)
# - header_inferred (bool)
# - convenience properties: data_first_row, has_data_rows, data_row_count, col_count
# - range refs: ref, header_ref, data_ref


# -----------------------------------------------------------------------------
# Shared state namespacing
# -----------------------------------------------------------------------------
# `state` is a mutable dict shared across the run.
# Best practice: store everything your config package needs under ONE top-level key.
#
# IMPORTANT: Keep this constant the same across *all* your hooks so they can share state.
STATE_NAMESPACE = "ade.config_package_template"
STATE_SCHEMA_VERSION = 1


# -----------------------------------------------------------------------------
# Polars convenience: string dtype selection across versions
# -----------------------------------------------------------------------------
_TEXT_DTYPES: list[pl.DataType] = []
for _attr in ("String", "Utf8"):
    _dt = getattr(pl, _attr, None)
    if _dt is not None:
        _TEXT_DTYPES.append(_dt)
TEXT_DTYPE: pl.DataType = _TEXT_DTYPES[0] if _TEXT_DTYPES else pl.Utf8  # type: ignore[attr-defined]


# Common "this means empty" tokens encountered in spreadsheets.
DEFAULT_EMPTY_SENTINELS: tuple[str, ...] = (
    "",
    "n/a",
    "na",
    "null",
    "none",
    "-",
    "—",  # em dash
    "–",  # en dash
    "nan",
)


def register(registry) -> None:
    """Register this config package's `on_table_mapped` hook(s)."""

    # Default (safe) no-op hook: records lightweight stats + logs table shape.
    registry.register_hook(on_table_mapped, hook="on_table_mapped", priority=0)

    # ---------------------------------------------------------------------
    # Examples (uncomment to enable, then customize as needed)
    # ---------------------------------------------------------------------
    # registry.register_hook(on_table_mapped_example_1_basic_cleanup, hook="on_table_mapped", priority=10)
    # registry.register_hook(on_table_mapped_example_2_trim_all_string_columns, hook="on_table_mapped", priority=20)
    # registry.register_hook(on_table_mapped_example_3_normalize_empty_sentinels, hook="on_table_mapped", priority=30)
    # registry.register_hook(on_table_mapped_example_4_drop_fully_empty_rows, hook="on_table_mapped", priority=40)
    # registry.register_hook(on_table_mapped_example_5_drop_fully_empty_columns, hook="on_table_mapped", priority=50)
    # registry.register_hook(on_table_mapped_example_6_derive_full_name, hook="on_table_mapped", priority=60)
    # registry.register_hook(on_table_mapped_example_7_drop_repeated_header_rows, hook="on_table_mapped", priority=70)
    # registry.register_hook(on_table_mapped_example_8_record_table_facts, hook="on_table_mapped", priority=80)
    # registry.register_hook(on_table_mapped_example_9_split_full_name, hook="on_table_mapped", priority=90)


# ---------------------------------------------------------------------------
# Default hook (enabled by default)
# ---------------------------------------------------------------------------


def on_table_mapped(
    *,
    settings,  # Engine Settings
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    workbook: openpyxl.Workbook | None,  # None for this stage (table hooks run before output workbook exists)
    sheet: openpyxl.worksheet.worksheet.Worksheet,  # Source worksheet (openpyxl Worksheet)
    table: pl.DataFrame,
    table_region: TableRegion | None,  # header_row/first_col/last_row/last_col (1-based, inclusive) + header_inferred; refs: ref/header_ref/data_ref
    table_index: int | None,  # 0-based table index within the sheet
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> pl.DataFrame | None:
    """Default: increment a counter and log the table shape (does not mutate `table`)."""
    _ = (settings, workbook, input_file_name)  # unused by default

    cfg = state.get(STATE_NAMESPACE)
    if not isinstance(cfg, MutableMapping):
        cfg = {}
        state[STATE_NAMESPACE] = cfg
    cfg.setdefault("schema_version", STATE_SCHEMA_VERSION)

    counters = cfg.get("counters")
    if not isinstance(counters, MutableMapping):
        counters = {}
        cfg["counters"] = counters
    counters["tables_seen"] = int(counters.get("tables_seen", 0) or 0) + 1

    sheet_name = str(getattr(sheet, "title", None) or getattr(sheet, "name", None) or "")
    if logger:
        range_ref = table_region.ref if table_region else "<unknown>"
        logger.info(
            "Config hook: table mapped (sheet=%s, table_index=%s, range=%s, rows=%d, columns=%d)",
            sheet_name,
            table_index if table_index is not None else "<unknown>",
            range_ref,
            int(table.height),
            int(table.width),
        )

    return None


# ---------------------------------------------------------------------------
# Example hooks (disabled by default)
# ---------------------------------------------------------------------------


def on_table_mapped_example_1_basic_cleanup(
    *,
    settings,
    metadata: dict,
    state: dict,
    workbook: openpyxl.Workbook | None,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    table: pl.DataFrame,
    table_region: TableRegion | None,  # See `TableRegion` notes above
    table_index: int | None,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame:
    """Example 1 (recommended): basic, safe cleanup for most table-like extracts.

    Includes:
    - Trim all string columns
    - Normalize common empty sentinels to null (case-insensitive)
    - Drop rows that are entirely empty (null/blank strings)

    This is deliberately conservative and avoids type coercion.
    """
    _ = (settings, metadata, state, workbook, table_region, table_index, input_file_name)

    before_rows, before_cols = int(table.height), int(table.width)

    # 1) Normalize empty sentinels across *string* columns.
    #    We apply the rule to all string columns in one shot, keeping original names.
    tokens = [t.strip().lower() for t in DEFAULT_EMPTY_SENTINELS]

    trimmed = pl.col(_TEXT_DTYPES).cast(TEXT_DTYPE, strict=False).str.strip_chars()
    lowered = trimmed.str.to_lowercase()

    cleaned = table.with_columns(
        pl.when(lowered.is_in(tokens))
        .then(pl.lit(None))
        .otherwise(trimmed)
        .name.keep()
    )

    # 2) Drop fully-empty rows (all columns are null/blank).
    if cleaned.width > 0:
        non_empty_exprs: list[pl.Expr] = []
        for name, dtype in cleaned.schema.items():
            col = pl.col(name)
            if dtype in _TEXT_DTYPES:
                s = col.cast(TEXT_DTYPE, strict=False).str.strip_chars()
                non_empty_exprs.append(s.is_not_null() & (s != ""))
            else:
                non_empty_exprs.append(col.is_not_null())

        cleaned = cleaned.filter(pl.any_horizontal(non_empty_exprs))

    after_rows, after_cols = int(cleaned.height), int(cleaned.width)

    if logger and (after_rows != before_rows or after_cols != before_cols):
        sheet_name = str(getattr(sheet, "title", None) or getattr(sheet, "name", None) or "")
        logger.info(
            "Basic cleanup: rows %d->%d, cols %d->%d (sheet=%s)",
            before_rows,
            after_rows,
            before_cols,
            after_cols,
            sheet_name,
        )

    return cleaned


def on_table_mapped_example_2_trim_all_string_columns(
    *,
    settings,
    metadata: dict,
    state: dict,
    workbook: openpyxl.Workbook | None,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    table: pl.DataFrame,
    table_region: TableRegion | None,  # See `TableRegion` notes above
    table_index: int | None,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame:
    """Example 2: trim all string columns (safe, cheap, and often helpful)."""
    _ = (settings, metadata, state, workbook, sheet, table_region, table_index, input_file_name, logger)

    return table.with_columns(pl.col(_TEXT_DTYPES).str.strip_chars().name.keep())


def on_table_mapped_example_3_normalize_empty_sentinels(
    *,
    settings,
    metadata: dict,
    state: dict,
    workbook: openpyxl.Workbook | None,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    table: pl.DataFrame,
    table_region: TableRegion | None,  # See `TableRegion` notes above
    table_index: int | None,
    input_file_name: str | None,
    logger,
    empty_sentinels: Sequence[str] = DEFAULT_EMPTY_SENTINELS,
) -> pl.DataFrame:
    """Example 3: normalize common 'empty' tokens to null across all string columns."""
    _ = (settings, metadata, state, workbook, sheet, table_region, table_index, input_file_name, logger)

    tokens = [t.strip().lower() for t in empty_sentinels]
    trimmed = pl.col(_TEXT_DTYPES).cast(TEXT_DTYPE, strict=False).str.strip_chars()
    lowered = trimmed.str.to_lowercase()

    return table.with_columns(
        pl.when(lowered.is_in(tokens))
        .then(pl.lit(None))
        .otherwise(trimmed)
        .name.keep()
    )


def on_table_mapped_example_4_drop_fully_empty_rows(
    *,
    settings,
    metadata: dict,
    state: dict,
    workbook: openpyxl.Workbook | None,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    table: pl.DataFrame,
    table_region: TableRegion | None,  # See `TableRegion` notes above
    table_index: int | None,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame:
    """Example 4: drop rows that are entirely empty (null/blank strings)."""
    _ = (settings, metadata, state, workbook, table_region, table_index, input_file_name)

    if table.width == 0:
        return table

    non_empty_exprs: list[pl.Expr] = []
    for name, dtype in table.schema.items():
        col = pl.col(name)
        if dtype in _TEXT_DTYPES:
            s = col.cast(TEXT_DTYPE, strict=False).str.strip_chars()
            non_empty_exprs.append(s.is_not_null() & (s != ""))
        else:
            non_empty_exprs.append(col.is_not_null())

    before = int(table.height)
    out = table.filter(pl.any_horizontal(non_empty_exprs))

    if logger:
        removed = before - int(out.height)
        if removed:
            sheet_name = str(getattr(sheet, "title", None) or getattr(sheet, "name", None) or "")
            logger.info("Dropped %d fully-empty rows (sheet=%s)", removed, sheet_name)

    return out


def on_table_mapped_example_5_drop_fully_empty_columns(
    *,
    settings,
    metadata: dict,
    state: dict,
    workbook: openpyxl.Workbook | None,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    table: pl.DataFrame,
    table_region: TableRegion | None,  # See `TableRegion` notes above
    table_index: int | None,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame:
    """Example 5: drop columns that are entirely empty (useful for noisy extracts).

    "Empty" means:
    - for string columns: null or blank after trimming in every row
    - for non-string columns: null in every row
    """
    _ = (settings, metadata, state, workbook, table_region, table_index, input_file_name)

    if table.width == 0:
        return table

    before_cols = list(table.columns)

    # For each column, compute "does this column contain any meaningful value?"
    has_any_exprs: list[pl.Expr] = []
    for name, dtype in table.schema.items():
        if dtype in _TEXT_DTYPES:
            trimmed = pl.col(name).cast(TEXT_DTYPE, strict=False).str.strip_chars()
            meaningful = trimmed.is_not_null() & (trimmed != "")
            has_any_exprs.append(meaningful.any().alias(name))
        else:
            has_any_exprs.append(pl.col(name).is_not_null().any().alias(name))

    # `select` with aggregations returns a single-row DataFrame.
    keep_map = table.select(has_any_exprs).row(0, named=True)
    keep_cols = [name for name in table.columns if bool(keep_map.get(name))]

    # If everything would be dropped, keep the original (safer for downstream).
    if not keep_cols or keep_cols == before_cols:
        return table

    out = table.select(keep_cols)

    if logger:
        removed_cols = [c for c in before_cols if c not in set(out.columns)]
        if removed_cols:
            sheet_name = str(getattr(sheet, "title", None) or getattr(sheet, "name", None) or "")
            logger.info(
                "Dropped %d empty columns (sheet=%s): %s",
                len(removed_cols),
                sheet_name,
                removed_cols,
            )

    return out


def on_table_mapped_example_6_derive_full_name(
    *,
    settings,
    metadata: dict,
    state: dict,
    workbook: openpyxl.Workbook | None,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    table: pl.DataFrame,
    table_region: TableRegion | None,  # See `TableRegion` notes above
    table_index: int | None,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame | None:
    """Example 6: derive `full_name` from `first_name` + `last_name`."""
    _ = (settings, metadata, state, workbook, sheet, table_region, table_index, input_file_name, logger)

    if "full_name" in table.columns:
        return None

    if "first_name" not in table.columns and "last_name" not in table.columns:
        return None

    first = (
        pl.col("first_name")
        .cast(TEXT_DTYPE, strict=False)
        .fill_null("")
        .str.strip_chars()
        if "first_name" in table.columns
        else pl.lit("", dtype=TEXT_DTYPE)
    )
    last = (
        pl.col("last_name")
        .cast(TEXT_DTYPE, strict=False)
        .fill_null("")
        .str.strip_chars()
        if "last_name" in table.columns
        else pl.lit("", dtype=TEXT_DTYPE)
    )

    full = pl.concat_str([first, last], separator=" ").str.strip_chars()
    full = pl.when(full == "").then(pl.lit(None)).otherwise(full).alias("full_name")

    return table.with_columns(full)


def on_table_mapped_example_7_drop_repeated_header_rows(
    *,
    settings,
    metadata: dict,
    state: dict,
    workbook: openpyxl.Workbook | None,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    table: pl.DataFrame,
    table_region: TableRegion | None,  # See `TableRegion` notes above
    table_index: int | None,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame | None:
    """Example 7 (heuristic): drop repeated header rows embedded inside the table.

    Many spreadsheets repeat the header every N rows (page breaks) or after section
    separators. A common pattern is a row where many cells match their column names.

    This is a heuristic: keep it disabled by default and tune the threshold.
    """
    _ = (settings, metadata, state, workbook, table_region, table_index, input_file_name)

    if table.width == 0 or table.height == 0:
        return None

    cols = list(table.columns)

    # Require that at least this fraction of columns match their header name.
    match_ratio = 0.80
    threshold = max(2, int(len(cols) * match_ratio))

    comparisons: list[pl.Expr] = []
    for name in cols:
        header_norm = name.strip().lower()
        cell_norm = (
            pl.col(name)
            .cast(TEXT_DTYPE, strict=False)
            .fill_null("")
            .str.strip_chars()
            .str.to_lowercase()
        )
        comparisons.append((cell_norm == pl.lit(header_norm)).cast(pl.Int8))

    match_count = pl.sum_horizontal(comparisons)
    out = table.filter(match_count < threshold)

    removed = int(table.height) - int(out.height)
    if logger and removed:
        sheet_name = str(getattr(sheet, "title", None) or getattr(sheet, "name", None) or "")
        logger.info(
            "Dropped %d repeated header-like rows (sheet=%s, threshold=%d/%d)",
            removed,
            sheet_name,
            threshold,
            len(cols),
        )

    return out if removed else None


def on_table_mapped_example_8_record_table_facts(
    *,
    settings,
    metadata: dict,
    state: dict,
    workbook: openpyxl.Workbook | None,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    table: pl.DataFrame,
    table_region: TableRegion | None,  # See `TableRegion` notes above
    table_index: int | None,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame | None:
    """Example 8: collect lightweight per-table facts into shared state."""
    _ = (settings, metadata, workbook, logger)

    cfg = state.get(STATE_NAMESPACE)
    if not isinstance(cfg, MutableMapping):
        cfg = {}
        state[STATE_NAMESPACE] = cfg

    tables = cfg.get("tables_mapped")
    if not isinstance(tables, list):
        tables = []
        cfg["tables_mapped"] = tables

    sheet_name = str(getattr(sheet, "title", None) or getattr(sheet, "name", None) or "")
    tables.append(
        {
            "input_file": input_file_name,
            "sheet": sheet_name,
            "table_index": table_index,
            "source_range": table_region.ref if table_region else None,
            "rows": int(table.height),
            "columns": list(table.columns),
        }
    )

    return None


def on_table_mapped_example_9_split_full_name(
    *,
    settings,
    metadata: dict,
    state: dict,
    workbook: openpyxl.Workbook | None,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    table: pl.DataFrame,
    table_region: TableRegion | None,  # See `TableRegion` notes above
    table_index: int | None,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame | None:
    """Example 9: split `full_name` into `first_name` and `last_name`.

    Notes:
    - Runs after mapping and before per-column transforms.
    - Does not overwrite existing first/last values when present.
    """
    _ = (settings, metadata, state, workbook, sheet, table_region, table_index, input_file_name, logger)

    if "full_name" not in table.columns:
        return None

    full = pl.col("full_name").cast(TEXT_DTYPE, strict=False).str.strip_chars()
    full = full.str.replace_all(r"\s+", " ")
    full = pl.when(full.is_null() | (full == "")).then(pl.lit(None)).otherwise(full)

    has_comma = full.str.contains(",").fill_null(False)

    comma_parts = full.str.split(",")
    comma_last = comma_parts.list.get(0, null_on_oob=True).cast(TEXT_DTYPE, strict=False).str.strip_chars()
    comma_first = comma_parts.list.get(1, null_on_oob=True).cast(TEXT_DTYPE, strict=False).str.strip_chars()

    space_parts = full.str.split(" ")
    space_len = space_parts.list.len()
    space_first = space_parts.list.get(0, null_on_oob=True).cast(TEXT_DTYPE, strict=False).str.strip_chars()
    space_last = (
        pl.when(space_len >= 2)
        .then(space_parts.list.get(-1, null_on_oob=True).cast(TEXT_DTYPE, strict=False).str.strip_chars())
        .otherwise(pl.lit(None))
    )

    derived_first = pl.when(has_comma).then(comma_first).otherwise(space_first)
    derived_last = pl.when(has_comma).then(comma_last).otherwise(space_last)

    derived_first = pl.when(derived_first.is_null() | (derived_first == "")).then(pl.lit(None)).otherwise(derived_first)
    derived_last = pl.when(derived_last.is_null() | (derived_last == "")).then(pl.lit(None)).otherwise(derived_last)

    if "first_name" in table.columns:
        existing_first = pl.col("first_name").cast(TEXT_DTYPE, strict=False).str.strip_chars()
        existing_first = pl.when(existing_first.is_null() | (existing_first == "")).then(pl.lit(None)).otherwise(
            existing_first
        )
        first_out = pl.coalesce([existing_first, derived_first]).alias("first_name")
    else:
        first_out = derived_first.alias("first_name")

    if "last_name" in table.columns:
        existing_last = pl.col("last_name").cast(TEXT_DTYPE, strict=False).str.strip_chars()
        existing_last = pl.when(existing_last.is_null() | (existing_last == "")).then(pl.lit(None)).otherwise(
            existing_last
        )
        last_out = pl.coalesce([existing_last, derived_last]).alias("last_name")
    else:
        last_out = derived_last.alias("last_name")

    return table.with_columns(first_out, last_out)
