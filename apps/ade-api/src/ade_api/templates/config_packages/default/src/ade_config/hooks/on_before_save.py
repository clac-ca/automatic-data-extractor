"""on_before_save hook that styles the workbook.

Runs after NormalizedTable objects have been produced and written into an
openpyxl Workbook, but before the engine saves it to disk.
"""

from __future__ import annotations

from typing import Any

from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo


def run(
    *,
    workbook: Any | None = None,         # openpyxl Workbook
    tables: list[Any] | None = None,     # NormalizedTable[]
    run: Any | None = None,
    manifest: Any | None = None,
    state: dict[str, Any] | None = None,
    logger: Any | None = None,
    stage: Any | None = None,
    result: Any | None = None,
    **_: Any,
) -> Any | None:
    """
    on_before_save: decorate or replace the normalized workbook.

    The engine will save whatever Workbook you return here.

    Return:
        - Workbook: the workbook to save (often the same `workbook` after mutation).
        - None: keep and save the original workbook object.
    """
    if workbook is None:
        return None

    sheet = workbook.active  # normalized worksheet
    sheet.freeze_panes = "A2"

    right = get_column_letter(sheet.max_column)
    table_ref = f"A1:{right}{sheet.max_row}"

    excel_table = Table(displayName="NormalizedData", ref=table_ref)
    excel_table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showRowStripes=True,
    )
    sheet.add_table(excel_table)

    if logger is not None:
        logger.note("Styled workbook with Excel table", stage=stage)

    return workbook
