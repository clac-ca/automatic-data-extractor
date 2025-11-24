"""on_before_save hook that styles the workbook.

Runs after NormalizedTable objects have been produced and written into an
openpyxl Workbook, but before the engine saves it to disk.
"""

from __future__ import annotations

from typing import Any

from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo


def run(ctx: Any) -> None:
    """
    Convert the active sheet to an Excel table for readability.

    If you don't care about styling, you can safely delete this hook or
    strip it down.
    """
    workbook = getattr(ctx, "workbook", None)
    if workbook is None:
        return

    sheet = workbook.active
    sheet.freeze_panes = "A2"

    right = get_column_letter(sheet.max_column)
    table_ref = f"A1:{right}{sheet.max_row}"

    excel_table = Table(displayName="NormalizedData", ref=table_ref)
    excel_table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showRowStripes=True,
    )
    sheet.add_table(excel_table)
