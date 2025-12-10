from __future__ import annotations

from typing import Any

from ade_engine.registry.models import HookName

# Optional: set a desired canonical output order.
# If left as None, the engine's default ordering is used.
DESIRED_FIELD_ORDER: list[str] | None = None


def register(registry):
    registry.register_hook(on_table_written, hook_name=HookName.ON_TABLE_WRITTEN, priority=0)


def on_table_written(
    *,
    hook_name,
    metadata,
    state,
    workbook,
    sheet,
    table,
    input_file_name,
    logger,
) -> None:
    """Called after a table has been written to the output workbook."""

    if logger and table:
        logger.info(
            "Config hook: table written (rows=%d, issues=%d)",
            len(getattr(table, "rows", []) or []),
            len(getattr(table, "issues", []) or []),
        )

    if DESIRED_FIELD_ORDER:
        reorder_table_columns_in_place(sheet, DESIRED_FIELD_ORDER)


def reorder_table_columns_in_place(sheet: Any, desired_headers: list[str]) -> None:
    """Reorder columns in the rendered sheet by header name (no insert/delete)."""

    if sheet is None or not desired_headers:
        return

    header_rows = list(sheet.iter_rows(min_row=1, max_row=1))
    if not header_rows:
        return

    header_values = [str(cell.value or "") for cell in header_rows[0]]
    index_by_header = {h: idx for idx, h in enumerate(header_values)}

    desired_idxs = [index_by_header[h] for h in desired_headers if h in index_by_header]
    remaining_idxs = [i for i in range(len(header_values)) if i not in desired_idxs]
    new_order = desired_idxs + remaining_idxs

    max_row = sheet.max_row or 0
    max_col = sheet.max_column or 0
    if max_row == 0 or max_col == 0:
        return

    # Snapshot grid
    grid: list[list[Any]] = [
        [sheet.cell(row=r, column=c).value for c in range(1, max_col + 1)]
        for r in range(1, max_row + 1)
    ]

    # Rewrite in new order
    for r_idx, row_values in enumerate(grid, start=1):
        for out_col, src_idx in enumerate(new_order, start=1):
            sheet.cell(row=r_idx, column=out_col).value = row_values[src_idx]
