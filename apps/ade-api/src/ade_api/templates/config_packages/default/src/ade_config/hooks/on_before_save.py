"""
Example: `on_before_save` hook

This hook runs AFTER:
    • NormalizedTable objects have been produced
    • The engine has already written them into an openpyxl Workbook

…and BEFORE the engine saves the workbook to disk.

Common use cases:
    • Apply Excel styling
    • Add tables, formatting, or freeze panes
    • Insert metadata sheets
    • Replace the workbook entirely with a custom one
    • Inject formulas, totals, charts, etc.

Whatever Workbook you return here is what the engine will save.
"""

from __future__ import annotations

from typing import Any

from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

# ---------------------------------------------------------------------------
# HOOK ENTRYPOINT
# ---------------------------------------------------------------------------

def run(
    *,
    workbook: Any | None = None,        # openpyxl Workbook
    tables: list[Any] | None = None,    # NormalizedTable[]
    run: Any | None = None,
    file_names: tuple[str, ...] | None = None,
    manifest: Any | None = None,
    state: dict[str, Any] | None = None,
    logger=None,
    event_emitter=None,
    stage: Any | None = None,
    result: Any | None = None,
    **_: Any,
) -> Any | None:
    """
    Main entrypoint for the `on_before_save` hook.

    Return:
        • Workbook → engine saves the returned workbook
        • None     → engine saves the original workbook passed in

    This example decorates the normalized worksheet by:
        • freezing the header row
        • wrapping the whole region in an Excel table
        • applying a clean table style
    """

    if workbook is None:
        return None

    # -----------------------------------------------------------------------
    # EXAMPLE: Apply simple formatting to the first worksheet
    # -----------------------------------------------------------------------

    sheet = workbook.active  # target normalized worksheet

    # Freeze header row (keeps column titles visible while scrolling)
    sheet.freeze_panes = "A2"

    # Create a table spanning all rows/columns of the sheet
    last_col = get_column_letter(sheet.max_column)
    table_ref = f"A1:{last_col}{sheet.max_row}"

    excel_table = Table(displayName="NormalizedData", ref=table_ref)
    excel_table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showRowStripes=True,
    )

    sheet.add_table(excel_table)

    # Logging + event hooks
    logger and logger.info("on_before_save: applied basic styling to workbook")

    # Returning the workbook means: "save this one"
    return workbook
