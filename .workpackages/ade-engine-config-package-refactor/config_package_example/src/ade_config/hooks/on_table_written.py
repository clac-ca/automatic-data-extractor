from __future__ import annotations

from typing import Any

from ade_engine.registry import hook


# Optional: set a desired canonical output order.
# If left as None, the engine's default ordering is used.
DESIRED_FIELD_ORDER: list[str] | None = None


@hook("on_table_written")
def run(*, table_ctx: Any, sheet_ctx: Any, run_ctx: Any, logger: Any | None = None, **_: Any) -> None:
    """Called after a table has been written to the output workbook.

    This is the best place to:
      - style the output range (header bold, column widths, number formats)
      - add comments
      - (optionally) reorder columns *in-place* by rewriting the table range

    Reordering is off by default. To enable, set DESIRED_FIELD_ORDER above.
    """
    if logger:
        logger.info("Config hook: table written")

    if not DESIRED_FIELD_ORDER:
        return

    view = getattr(table_ctx, "view", None)
    if view is None:
        return

    reorder_table_columns_in_place(view, DESIRED_FIELD_ORDER)


def reorder_table_columns_in_place(view: Any, desired_headers: list[str]) -> None:
    """Reorder columns inside an existing written table range (no insert/delete).

    This works by:
      1) reading the whole range into memory
      2) re-ordering columns by header name
      3) writing the reordered grid back into the same range

    This respects the hook safety contract because it doesn't insert/delete rows/cols.
    """
    ws = view.worksheet
    cr = view.cell_range  # openpyxl CellRange
    min_col, min_row, max_col, max_row = cr.min_col, cr.min_row, cr.max_col, cr.max_row

    # Read grid
    grid: list[list[Any]] = []
    for r in range(min_row, max_row + 1):
        row_vals: list[Any] = []
        for c in range(min_col, max_col + 1):
            row_vals.append(ws.cell(row=r, column=c).value)
        grid.append(row_vals)

    header = [str(x) if x is not None else "" for x in grid[0]]
    index_by_header = {h: i for i, h in enumerate(header)}

    # Build new column order: desired headers first, then everything else
    desired_idxs = [index_by_header[h] for h in desired_headers if h in index_by_header]
    remaining_idxs = [i for i in range(len(header)) if i not in desired_idxs]
    new_order = desired_idxs + remaining_idxs

    # Reorder
    new_grid = []
    for row in grid:
        new_grid.append([row[i] for i in new_order])

    # Write back
    for r_off, r in enumerate(range(min_row, max_row + 1)):
        for c_off, c in enumerate(range(min_col, max_col + 1)):
            ws.cell(row=r, column=c).value = new_grid[r_off][c_off]
