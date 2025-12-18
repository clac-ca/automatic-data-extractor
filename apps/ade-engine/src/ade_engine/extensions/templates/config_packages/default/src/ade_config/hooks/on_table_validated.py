from __future__ import annotations

import polars as pl

ISSUE_COL_PREFIX = "__ade_issue__"
HAS_ISSUES_COL = "__ade_has_issues"
ISSUE_COUNT_COL = "__ade_issue_count"

# Optional: set a desired output order for your canonical fields.
# Example:
# DESIRED_FIELD_ORDER = ["member_id", "dob", "gender"]
DESIRED_FIELD_ORDER: list[str] | None = None


def register(registry):
    registry.register_hook(on_table_validated, hook="on_table_validated", priority=0)


# ---------------------------------------------------------------------------
# Hook: on_table_validated
#
# When it runs:
# - Called once per detected table, after validators have run and added ADE's
#   reserved issue columns, but before the output is written.
#
# What it's good for:
# - Output shaping: reorder/select columns, add derived columns, and sort/filter
#   rows for downstream consumption.
# - Triaging data quality: move "bad" rows to the top, or produce a "valid-only"
#   output by filtering out rows with issues.
#
# Reserved validation columns available in `table` at this point:
# - `__ade_has_issues` (bool): row has any issues
# - `__ade_issue_count` (int): count of fields with issues in the row
# - `__ade_issue__<field>` (str): per-field issue message (null when ok); these
#   are only present for fields that have validators registered.
#
# Tip: this is the last "table-returning" hook. If you need values to be
# re-validated, change them earlier in `on_table_transformed`.
# ---------------------------------------------------------------------------
def on_table_validated(
    *,
    hook_name,  # HookName enum value for this stage
    settings,  # Engine Settings
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    workbook,  # None for this stage (table hooks run before output workbook exists)
    sheet,  # Source worksheet (openpyxl Worksheet)
    table: pl.DataFrame,  # Current table DF (post-validation; pre-write)
    write_table,  # None for this stage
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> pl.DataFrame | None:
    """Post-validation hook (pre-write).

    Return a new DataFrame to replace ``table`` (or return None to keep it).
    """

    if logger:
        issues_total = 0
        rows_with_issues = 0
        if ISSUE_COUNT_COL in table.columns:
            issues_total = int(table.get_column(ISSUE_COUNT_COL).sum() or 0)
        if HAS_ISSUES_COL in table.columns:
            rows_with_issues = int(table.get_column(HAS_ISSUES_COL).sum() or 0)
        logger.info(
            "Config hook: table validated (issues_total=%d rows_with_issues=%d)",
            issues_total,
            rows_with_issues,
        )

    if DESIRED_FIELD_ORDER:
        desired = [c for c in DESIRED_FIELD_ORDER if c in table.columns]
        remaining = [c for c in table.columns if c not in desired]
        return table.select(desired + remaining)

    # Examples (uncomment one):
    #
    # # 1) Drop rows that have issues (valid-only output).
    # if HAS_ISSUES_COL in table.columns:
    #     return table.filter(~pl.col(HAS_ISSUES_COL))
    #
    # # 2) Keep only rows that have issues (exceptions-only output).
    # if HAS_ISSUES_COL in table.columns:
    #     return table.filter(pl.col(HAS_ISSUES_COL))
    #
    # # 3) Sort so the most problematic rows appear first.
    # if ISSUE_COUNT_COL in table.columns:
    #     return table.sort(ISSUE_COUNT_COL, descending=True)
    #
    # # 4) Move ADE's reserved issue columns to the end (nicer for humans).
    # issue_cols = [c for c in table.columns if c.startswith(ISSUE_COL_PREFIX)]
    # tail = [HAS_ISSUES_COL, ISSUE_COUNT_COL, *issue_cols]
    # tail = [c for c in tail if c in table.columns]
    # head = [c for c in table.columns if c not in tail]
    # return table.select([*head, *tail])
    #
    # # 5) Add a single summary column that concatenates all issue messages.
    # issue_cols = [c for c in table.columns if c.startswith(ISSUE_COL_PREFIX)]
    # if issue_cols:
    #     return table.with_columns(
    #         pl.concat_str(
    #             [pl.col(c) for c in issue_cols],
    #             separator="; ",
    #             ignore_nulls=True,
    #         ).alias("issues_summary")
    #     )

    return None
