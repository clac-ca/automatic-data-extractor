"""Renderer that writes normalized tables into an openpyxl worksheet."""

from __future__ import annotations

from openpyxl.worksheet.cell_range import CellRange
from openpyxl.worksheet.worksheet import Worksheet

from ade_engine.pipeline.layout import SheetLayout
from ade_engine.types.origin import TablePlacement
from ade_engine.types.tables import NormalizedTable


class TableRenderer:
    def __init__(self, layout: SheetLayout | None = None) -> None:
        self.layout = layout or SheetLayout()

    def write_table(self, worksheet: Worksheet, table: NormalizedTable) -> TablePlacement:
        start_row = self.layout.next_row
        start_col = 1

        for col_index, name in enumerate(table.header, start=start_col):
            worksheet.cell(row=start_row, column=col_index, value=name)

        for row_offset, row_values in enumerate(table.rows, start=1):
            for col_offset, value in enumerate(row_values, start=0):
                worksheet.cell(row=start_row + row_offset, column=start_col + col_offset, value=value)

        width = max(len(table.header), max((len(r) for r in table.rows), default=0), 1)
        end_row = start_row + len(table.rows)
        end_col = start_col + width - 1

        self.layout.next_row = end_row + self.layout.blank_rows_between_tables + 1
        cell_range = CellRange(min_col=start_col, min_row=start_row, max_col=end_col, max_row=end_row)

        return TablePlacement(worksheet=worksheet, cell_range=cell_range, origin=table.origin)


__all__ = ["TableRenderer"]
