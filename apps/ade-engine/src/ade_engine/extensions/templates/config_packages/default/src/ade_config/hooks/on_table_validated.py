"""ADE config hook: `on_table_validated`

When this runs
--------------
- Once per detected table, after validators have run and ADE's reserved issue columns
  have been added, but before the output is written.

Reserved validation columns
---------------------------
- `__ade_has_issues` (bool): row has any issues
- `__ade_issue_count` (int): count of fields with issues in the row
- `__ade_issue__<field>` (str): per-field issue message (null/blank when ok)
  (these exist only for fields that have validators registered)

What it's useful for
--------------------
- Final output shaping: reorder/select columns, add derived columns, sort/filter rows
- Triage data quality: move issue rows to the top, add human-friendly summaries

Return value
------------
- Return a new `pl.DataFrame` to replace `table`, or `None` to keep it unchanged.
- Returning anything else raises HookError.

Notes
-----
- This is the last "table-returning" hook. If you change values here, validators
  will NOT re-run. Do value changes earlier in `on_table_transformed`.
- `workbook` is the *input* workbook (openpyxl Workbook).
- ADE passes `table_region` (a `TableRegion`) describing the source header+data block in the
  input sheet using 1-based, inclusive (openpyxl-friendly) coordinates.
- `table_index` is a 0-based index within the sheet (useful when a sheet has multiple tables).

Template goals
--------------
- Default hook is safe and minimal (logs + lightweight counters).
- Examples are self-contained and opt-in (uncomment in `register()`).
"""

from __future__ import annotations

from collections.abc import MutableMapping

import openpyxl
import openpyxl.worksheet.worksheet
import polars as pl
from ade_engine.models import TableRegion


def register(registry) -> None:
    """Register this config package's `on_table_validated` hook(s)."""
    registry.register_hook(on_table_validated, hook="on_table_validated", priority=0)

    # Examples (uncomment to enable)
    # registry.register_hook(on_table_validated_example_1_enforce_template_layout, hook="on_table_validated", priority=10)
    # registry.register_hook(on_table_validated_example_2_strict_template_only, hook="on_table_validated", priority=20)
    # registry.register_hook(on_table_validated_example_3_add_derived_columns, hook="on_table_validated", priority=30)
    # registry.register_hook(on_table_validated_example_4_sort_issues_to_top, hook="on_table_validated", priority=40)
    # registry.register_hook(on_table_validated_example_5_move_issue_columns_to_end, hook="on_table_validated", priority=50)
    # registry.register_hook(on_table_validated_example_6_add_issues_summary_column, hook="on_table_validated", priority=60)
    # registry.register_hook(on_table_validated_example_7_enrich_from_reference_csv_cached, hook="on_table_validated", priority=70)


def on_table_validated(
    *,
    table: pl.DataFrame,  # Current table DF (post-validation; pre-write)
    sheet: openpyxl.worksheet.worksheet.Worksheet,  # Source worksheet (openpyxl Worksheet)
    workbook: openpyxl.Workbook,  # Input workbook (openpyxl Workbook)
    table_region: TableRegion,  # Excel coords via .min_row/.max_row/.min_col/.max_col; helpers .a1/.header_row/.data_first_row
    table_index: int,  # 0-based table index within the sheet
    input_file_name: str,  # Input filename (basename)
    settings,  # Engine Settings
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    logger,  # RunLogger (structured events + text logs)
) -> pl.DataFrame | None:
    """Default: log a small issue summary and keep the table unchanged."""
    _ = (settings, metadata, workbook, input_file_name)

    has_issues_col = "__ade_has_issues"
    issue_count_col = "__ade_issue_count"

    cfg = state

    counters = cfg.get("counters")
    if not isinstance(counters, MutableMapping):
        counters = {}
        cfg["counters"] = counters
    counters["tables_validated_seen"] = int(counters.get("tables_validated_seen", 0) or 0) + 1

    if logger:
        sheet_name = getattr(sheet, "title", getattr(sheet, "name", ""))
        range_ref = table_region.a1
        issues_total = 0
        rows_with_issues = 0

        if issue_count_col in table.columns:
            issues_total = int(table.get_column(issue_count_col).sum() or 0)
        if has_issues_col in table.columns:
            rows_with_issues = int(table.get_column(has_issues_col).sum() or 0)

        logger.info(
            "Config hook: table validated (sheet=%s table_index=%s range=%s rows=%d cols=%d issues_total=%d rows_with_issues=%d)",
            sheet_name,
            table_index,
            range_ref,
            int(table.height),
            int(len(table.columns)),
            issues_total,
            rows_with_issues,
        )

    return None


# -------------------------------------------------------------------------
# EXAMPLE 1: Enforce a canonical layout (add missing columns + reorder)
# -------------------------------------------------------------------------


def on_table_validated_example_1_enforce_template_layout(
    *,
    table: pl.DataFrame,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    workbook: openpyxl.Workbook,
    table_region: TableRegion,  # See `TableRegion` notes above
    table_index: int,
    input_file_name: str,
    settings,
    metadata: dict,
    state: dict,
    logger,
) -> pl.DataFrame:
    """Example 1: enforce a spreadsheet-style output layout.

    Pattern:
    - Define the columns your downstream spreadsheet expects, in the exact order you want.
    - If a required column is missing, ADD it as an empty column (nulls).
    - Keep unexpected columns, but append them to the right.
    - Keep ADE issue columns at the far right (so they don't break templates).
    """
    _ = (settings, metadata, state, workbook, sheet, table_region, table_index, input_file_name)

    issue_col_prefix = "__ade_issue__"
    has_issues_col = "__ade_has_issues"
    issue_count_col = "__ade_issue_count"

    # 1) Define your required template columns (name + dtype).
    #    - We only enforce types for columns we ADD here.
    #    - We do NOT cast existing columns (validators won't re-run at this stage).
    TEMPLATE_COLUMNS: list[tuple[str, pl.DataType]] = [
        ("member_id", pl.Utf8),
        ("first_name", pl.Utf8),
        ("last_name", pl.Utf8),
        ("dob", pl.Utf8),  # keep as text here; parse earlier if you want validation
        ("gender", pl.Utf8),
        ("email", pl.Utf8),
        ("phone", pl.Utf8),
        ("address_1", pl.Utf8),
        ("address_2", pl.Utf8),
        ("city", pl.Utf8),
        ("state", pl.Utf8),
        ("postal_code", pl.Utf8),
    ]
    required_names = [name for name, _dtype in TEMPLATE_COLUMNS]

    # 2) Add missing template columns as empty (null) columns.
    missing_exprs: list[pl.Expr] = []
    for name, dtype in TEMPLATE_COLUMNS:
        if name not in table.columns:
            missing_exprs.append(pl.lit(None, dtype=dtype).alias(name))
    if missing_exprs:
        table = table.with_columns(missing_exprs)
        if logger:
            logger.info(
                "Enforced template: added missing columns=%s",
                [e.meta.output_name() for e in missing_exprs],
            )

    # 3) Identify ADE's reserved issue columns.
    issue_cols = [c for c in table.columns if c.startswith(issue_col_prefix)]
    reserved_tail = [has_issues_col, issue_count_col, *issue_cols]
    reserved_tail = [c for c in reserved_tail if c in table.columns]

    # 4) Build final column order.
    other_cols = [c for c in table.columns if c not in required_names and c not in reserved_tail]
    final_cols = [*required_names, *other_cols, *reserved_tail]

    # 5) Select in that order (reorders columns without touching values).
    return table.select(final_cols)


# -------------------------------------------------------------------------
# EXAMPLE 2: Strict template (output only the template columns)
# -------------------------------------------------------------------------


def on_table_validated_example_2_strict_template_only(
    *,
    table: pl.DataFrame,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    workbook: openpyxl.Workbook,
    table_region: TableRegion,  # See `TableRegion` notes above
    table_index: int,
    input_file_name: str,
    settings,
    metadata: dict,
    state: dict,
    logger,
) -> pl.DataFrame:
    """Example 2: strict template output.

    - Ensures a required set of columns exist (adds empty ones if missing).
    - Outputs ONLY those columns (drops everything else).
    - Optionally includes ADE issue columns at the end.
    """
    _ = (
        settings,
        metadata,
        state,
        workbook,
        sheet,
        table_region,
        table_index,
        input_file_name,
        logger,
    )

    issue_col_prefix = "__ade_issue__"
    has_issues_col = "__ade_has_issues"
    issue_count_col = "__ade_issue_count"

    TEMPLATE_COLUMNS: list[tuple[str, pl.DataType]] = [
        ("member_id", pl.Utf8),
        ("first_name", pl.Utf8),
        ("last_name", pl.Utf8),
        ("dob", pl.Utf8),
        ("gender", pl.Utf8),
        ("email", pl.Utf8),
    ]
    required_names = [name for name, _dtype in TEMPLATE_COLUMNS]

    missing_exprs: list[pl.Expr] = []
    for name, dtype in TEMPLATE_COLUMNS:
        if name not in table.columns:
            missing_exprs.append(pl.lit(None, dtype=dtype).alias(name))
    if missing_exprs:
        table = table.with_columns(missing_exprs)

    issue_cols = [c for c in table.columns if c.startswith(issue_col_prefix)]
    reserved_tail = [has_issues_col, issue_count_col, *issue_cols]
    reserved_tail = [c for c in reserved_tail if c in table.columns]

    return table.select([*required_names, *reserved_tail])


# -------------------------------------------------------------------------
# EXAMPLE 3: Add derived columns (Polars expressions)
# -------------------------------------------------------------------------


def on_table_validated_example_3_add_derived_columns(
    *,
    table: pl.DataFrame,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    workbook: openpyxl.Workbook,
    table_region: TableRegion,  # See `TableRegion` notes above
    table_index: int,
    input_file_name: str,
    settings,
    metadata: dict,
    state: dict,
    logger,
) -> pl.DataFrame | None:
    """Example 3: add derived columns using Polars expressions (fast + readable).

    Demonstrates:
    - Building `full_name` from first/last name
    - Extracting an email domain
    - Normalizing a phone number to digits only (very basic)
    - Creating a simple `row_status` from ADE's issue columns
    """
    _ = (settings, metadata, state, workbook, sheet, table_region, table_index, input_file_name)

    has_issues_col = "__ade_has_issues"

    if not any(
        c in table.columns for c in ["first_name", "last_name", "email", "phone", has_issues_col]
    ):
        return None

    exprs: list[pl.Expr] = []

    # full_name = "first_name last_name" (handles nulls cleanly)
    if "first_name" in table.columns or "last_name" in table.columns:
        first = (
            pl.col("first_name").cast(pl.Utf8)
            if "first_name" in table.columns
            else pl.lit(None, dtype=pl.Utf8)
        )
        last = (
            pl.col("last_name").cast(pl.Utf8)
            if "last_name" in table.columns
            else pl.lit(None, dtype=pl.Utf8)
        )
        exprs.append(
            pl.concat_str(
                [
                    first.fill_null("").str.strip_chars(),
                    last.fill_null("").str.strip_chars(),
                ],
                separator=" ",
            )
            .str.strip_chars()
            .alias("full_name")
        )

    # email_domain = part after "@"
    if "email" in table.columns:
        exprs.append(
            pl.col("email")
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.to_lowercase()
            .str.extract(r"@(.+)$", 1)
            .alias("email_domain")
        )

    # phone_digits = keep digits only (very simple; adjust for your rules)
    if "phone" in table.columns:
        exprs.append(
            pl.col("phone").cast(pl.Utf8).str.replace_all(r"\D+", "").alias("phone_digits")
        )

    # row_status = "ISSUES" / "OK"
    if has_issues_col in table.columns:
        exprs.append(
            pl.when(pl.col(has_issues_col))
            .then(pl.lit("ISSUES"))
            .otherwise(pl.lit("OK"))
            .alias("row_status")
        )

    if not exprs:
        return None

    out = table.with_columns(exprs)

    if logger:
        logger.info("Added derived columns=%s", [e.meta.output_name() for e in exprs])

    return out


# -------------------------------------------------------------------------
# EXAMPLE 4: Sort so issue rows are first (triage-friendly)
# -------------------------------------------------------------------------


def on_table_validated_example_4_sort_issues_to_top(
    *,
    table: pl.DataFrame,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    workbook: openpyxl.Workbook,
    table_region: TableRegion,  # See `TableRegion` notes above
    table_index: int,
    input_file_name: str,
    settings,
    metadata: dict,
    state: dict,
    logger,
) -> pl.DataFrame | None:
    """Example 4: sort so rows with issues appear at the top (triage-friendly)."""
    _ = (
        settings,
        metadata,
        state,
        workbook,
        sheet,
        table_region,
        table_index,
        input_file_name,
        logger,
    )

    has_issues_col = "__ade_has_issues"
    issue_count_col = "__ade_issue_count"

    if has_issues_col not in table.columns and issue_count_col not in table.columns:
        return None

    by: list[str] = []
    descending: list[bool] = []

    if has_issues_col in table.columns:
        by.append(has_issues_col)
        descending.append(True)
    if issue_count_col in table.columns:
        by.append(issue_count_col)
        descending.append(True)

    # Optional stable sort keys (add them only if present).
    for key in ["member_id", "id", "row_number"]:
        if key in table.columns:
            by.append(key)
            descending.append(False)

    return table.sort(by=by, descending=descending) if by else None


# -------------------------------------------------------------------------
# EXAMPLE 5: Move ADE issue columns to the far right
# -------------------------------------------------------------------------


def on_table_validated_example_5_move_issue_columns_to_end(
    *,
    table: pl.DataFrame,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    workbook: openpyxl.Workbook,
    table_region: TableRegion,  # See `TableRegion` notes above
    table_index: int,
    input_file_name: str,
    settings,
    metadata: dict,
    state: dict,
    logger,
) -> pl.DataFrame | None:
    """Example 5: move ADE's reserved issue columns to the end (nicer for humans)."""
    _ = (
        settings,
        metadata,
        state,
        workbook,
        sheet,
        table_region,
        table_index,
        input_file_name,
        logger,
    )

    issue_col_prefix = "__ade_issue__"
    has_issues_col = "__ade_has_issues"
    issue_count_col = "__ade_issue_count"

    issue_cols = [c for c in table.columns if c.startswith(issue_col_prefix)]
    tail = [has_issues_col, issue_count_col, *issue_cols]
    tail = [c for c in tail if c in table.columns]
    if not tail:
        return None

    head = [c for c in table.columns if c not in tail]
    return table.select([*head, *tail])


# -------------------------------------------------------------------------
# EXAMPLE 6: Add a human-friendly issues summary column
# -------------------------------------------------------------------------


def on_table_validated_example_6_add_issues_summary_column(
    *,
    table: pl.DataFrame,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    workbook: openpyxl.Workbook,
    table_region: TableRegion,  # See `TableRegion` notes above
    table_index: int,
    input_file_name: str,
    settings,
    metadata: dict,
    state: dict,
    logger,
) -> pl.DataFrame | None:
    """Example 6: add a single `issues_summary` column + an `issue_fields` list column."""
    _ = (
        settings,
        metadata,
        state,
        workbook,
        sheet,
        table_region,
        table_index,
        input_file_name,
        logger,
    )

    issue_col_prefix = "__ade_issue__"
    issue_cols = [c for c in table.columns if c.startswith(issue_col_prefix)]
    if not issue_cols:
        return None

    summary_expr = (
        pl.concat_str(
            [pl.col(c).cast(pl.Utf8) for c in issue_cols],
            separator="; ",
            ignore_nulls=True,
        )
        .str.strip_chars()
        .alias("issues_summary")
    )

    field_name_exprs: list[pl.Expr] = []
    for c in issue_cols:
        field_name = c[len(issue_col_prefix) :]
        field_name_exprs.append(
            pl.when(pl.col(c).is_not_null() & (pl.col(c).cast(pl.Utf8) != ""))
            .then(pl.lit(field_name))
            .otherwise(None)
        )

    fields_expr = pl.concat_list(field_name_exprs).list.drop_nulls().alias("issue_fields")

    return table.with_columns([summary_expr, fields_expr])


# -------------------------------------------------------------------------
# EXAMPLE 7: Enrich from a reference CSV and cache it in `state`
# -------------------------------------------------------------------------


def on_table_validated_example_7_enrich_from_reference_csv_cached(
    *,
    table: pl.DataFrame,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    workbook: openpyxl.Workbook,
    table_region: TableRegion,  # See `TableRegion` notes above
    table_index: int,
    input_file_name: str,
    settings,
    metadata: dict,
    state: dict,
    logger,
) -> pl.DataFrame | None:
    """Example 7: enrich your output by joining to a reference dataset.

    Demonstrates:
    1) Cache expensive work (reading a CSV) in `state` so it happens once per run.
    2) Join enrichment via Polars (fast + readable).
    """
    _ = (settings, metadata, workbook, sheet, table_region, table_index, input_file_name)

    # --- Configuration you would customize ---
    REFERENCE_CSV_PATH = "member_reference.csv"  # <-- change me
    CACHE_KEY = "member_reference_df"
    JOIN_KEY = "member_id"

    if JOIN_KEY not in table.columns:
        return None

    cfg = state

    cache = cfg.get("cache")
    if not isinstance(cache, MutableMapping):
        cache = {}
        cfg["cache"] = cache

    # 1) Load (or reuse) the reference DataFrame.
    ref_df = cache.get(CACHE_KEY)
    if ref_df is None and CACHE_KEY not in cache:
        try:
            ref_df = pl.read_csv(REFERENCE_CSV_PATH)
            cache[CACHE_KEY] = ref_df
            if logger:
                logger.info(
                    "Loaded reference CSV for enrichment: path=%s rows=%d cols=%d",
                    REFERENCE_CSV_PATH,
                    int(ref_df.height),
                    int(len(ref_df.columns)),
                )
        except Exception as exc:
            cache[CACHE_KEY] = None
            if logger:
                logger.warning(
                    "Skipping enrichment: failed to read reference CSV path=%s error=%s",
                    REFERENCE_CSV_PATH,
                    repr(exc),
                )
            return None

    if ref_df is None or not isinstance(ref_df, pl.DataFrame):
        return None

    if JOIN_KEY not in ref_df.columns:
        if logger:
            logger.warning(
                "Skipping enrichment: reference CSV missing join key=%s (cols=%s)",
                JOIN_KEY,
                ref_df.columns,
            )
        return None

    # 2) Join (left join keeps all original rows).
    enriched = table.join(ref_df, on=JOIN_KEY, how="left")

    if logger:
        logger.info(
            "Enriched table via join: key=%s added_cols=%s",
            JOIN_KEY,
            [c for c in enriched.columns if c not in table.columns],
        )

    return enriched
