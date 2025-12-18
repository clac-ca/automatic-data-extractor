from __future__ import annotations

import polars as pl


# -----------------------------------------------------------------------------
# Hook: on_table_written
#
# When it runs:
# - Called once per detected table region, immediately AFTER ADE has rendered the
#   table into the OUTPUT workbook (openpyxl) and BEFORE the workbook is saved.
# - The table's cells already exist in `sheet` when this hook runs.
#
# What it's good for:
# - Applying worksheet/table formatting (freeze panes, filters, column widths,
#   number formats, conditional formatting)
# - Hiding helper/diagnostic columns that you still want to keep in the output
# - Recording post-write metrics into `state` for later use (e.g. in
#   `on_workbook_before_save`)
#
# Notes:
# - This hook MUST return None (returning anything else raises HookError).
# - If you need to change table values/shape, do it earlier:
#   `on_table_mapped` / `on_table_transformed` / `on_table_validated`.
# - `table` is the full post-validation DataFrame; `write_table` is the exact
#   DataFrame that was written (after output settings like dropping unmapped or
#   diagnostic columns).
# -----------------------------------------------------------------------------


def register(registry):
    registry.register_hook(on_table_written, hook="on_table_written", priority=0)

    # Examples (uncomment to enable)
    # registry.register_hook(on_table_written_example_1_log_output_range, hook="on_table_written", priority=0)
    # registry.register_hook(on_table_written_example_2_freeze_header_and_add_filters, hook="on_table_written", priority=0)
    # registry.register_hook(on_table_written_example_3_format_header_bold_wrap, hook="on_table_written", priority=0)
    # registry.register_hook(on_table_written_example_4_hide_diagnostic_columns, hook="on_table_written", priority=0)
    # registry.register_hook(on_table_written_example_5_collect_table_facts, hook="on_table_written", priority=0)


def on_table_written(
    *,
    hook_name,  # HookName enum value for this stage
    settings,  # Engine Settings
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    workbook,  # Output workbook (openpyxl Workbook)
    sheet,  # Output worksheet (openpyxl Worksheet)
    table: pl.DataFrame,  # Full in-memory table DF (post-validation)
    write_table: pl.DataFrame,  # Exact DF that was written (after output policies)
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> None:
    """
    Called after ADE writes a single normalized table to the output worksheet.

    Use this hook for Excel-only concerns (formatting, UX, summary/notes sheets).
    It must not modify the already-written table values.
    """

    sheet_name = getattr(sheet, "title", getattr(sheet, "name", ""))
    if logger:
        logger.info(
            "Config hook: table written (sheet=%s, rows=%d, columns=%d)",
            sheet_name,
            int(write_table.height),
            len(write_table.columns),
        )


def on_table_written_example_1_log_output_range(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table: pl.DataFrame,
    input_file_name: str | None,
    logger,
) -> None:
    """Example: compute the output range for THIS table and log it."""

    from openpyxl.utils import get_column_letter

    if len(write_table.columns) == 0:
        return
    max_row = getattr(sheet, "max_row", None)
    if not max_row:
        return

    header_row = int(max_row) - int(write_table.height)
    last_row = int(max_row)
    last_col = get_column_letter(len(write_table.columns))
    output_range = f"A{header_row}:{last_col}{last_row}"

    if logger:
        logger.info("Output range for last table: %s", output_range)


def on_table_written_example_2_freeze_header_and_add_filters(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table: pl.DataFrame,
    input_file_name: str | None,
    logger,
) -> None:
    """Example: freeze the header row and turn on filters for this table."""

    from openpyxl.utils import get_column_letter

    if len(write_table.columns) == 0:
        return
    max_row = getattr(sheet, "max_row", None)
    if not max_row:
        return

    header_row = int(max_row) - int(write_table.height)
    last_row = int(max_row)
    last_col = get_column_letter(len(write_table.columns))
    sheet.freeze_panes = f"A{header_row + 1}"
    sheet.auto_filter.ref = f"A{header_row}:{last_col}{last_row}"


def on_table_written_example_3_format_header_bold_wrap(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table: pl.DataFrame,
    input_file_name: str | None,
    logger,
) -> None:
    """Example: make the header row bold and wrap header text."""

    from openpyxl.styles import Alignment, Font

    if len(write_table.columns) == 0:
        return
    max_row = getattr(sheet, "max_row", None)
    if not max_row:
        return

    header_row = int(max_row) - int(write_table.height)
    header_font = Font(bold=True)
    header_alignment = Alignment(wrap_text=True, vertical="top")
    for col_idx in range(1, len(write_table.columns) + 1):
        cell = sheet.cell(row=header_row, column=col_idx)
        cell.font = header_font
        cell.alignment = header_alignment


def on_table_written_example_4_hide_diagnostic_columns(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table: pl.DataFrame,
    input_file_name: str | None,
    logger,
) -> None:
    """Example: hide ADE diagnostic columns (if you choose to keep them written)."""

    from openpyxl.utils import get_column_letter

    for idx, col_name in enumerate(write_table.columns, start=1):
        if col_name.startswith("__ade_"):
            sheet.column_dimensions[get_column_letter(idx)].hidden = True


def on_table_written_example_5_collect_table_facts(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table: pl.DataFrame,
    input_file_name: str | None,
    logger,
) -> None:
    """Example: collect per-table facts into shared state for later summary writing."""

    sheet_name = getattr(sheet, "title", getattr(sheet, "name", ""))
    tables = state.setdefault("tables", [])
    tables.append(
        {
            "input_file": input_file_name,
            "sheet": sheet_name,
            "rows": int(write_table.height),
            "columns": list(write_table.columns),
        }
    )
