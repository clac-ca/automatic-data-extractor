from __future__ import annotations

from openpyxl import Workbook

from ade_engine.pipeline.models import MappedColumn, SourceColumn, TableData
from ade_engine.pipeline.render import SheetWriter, render_table
from ade_engine.settings import Settings


class DummyLogger:
    def event(self, *args, **kwargs):
        pass


def test_render_includes_unmapped_rows_when_no_mapped_columns():
    wb = Workbook()
    ws = wb.active

    table = TableData(
        sheet_name="Sheet1",
        header_row_index=0,
        table_index=0,
        source_columns=[],
        mapped_columns=[],
        unmapped_columns=[
            SourceColumn(index=0, header="col_a", values=[1, 2]),
            SourceColumn(index=1, header="col_b", values=[3, 4]),
        ],
    )

    render_table(
        table=table,
        writer=SheetWriter(ws),
        settings=Settings(),
        logger=DummyLogger(),
    )

    # Expect header + two data rows
    assert ws.max_row == 3
    assert ws.max_column == 2
    assert [cell.value for cell in ws[1]] == ["raw_col_a", "raw_col_b"]
    assert [cell.value for cell in ws[2]] == [1, 3]
    assert [cell.value for cell in ws[3]] == [2, 4]


def test_render_row_count_uses_longest_of_mapped_and_unmapped():
    wb = Workbook()
    ws = wb.active

    mapped = [
        MappedColumn(field_name="field1", source_index=0, header="f1", values=["a"], score=1.0),
    ]
    unmapped = [
        SourceColumn(index=1, header="extra", values=[10, 20, 30]),
    ]

    table = TableData(
        sheet_name="Sheet1",
        header_row_index=0,
        table_index=0,
        source_columns=[],
        mapped_columns=mapped,
        unmapped_columns=unmapped,
        row_count=1,
        columns={"field1": ["a"]},
    )

    render_table(
        table=table,
        writer=SheetWriter(ws),
        settings=Settings(),
        logger=DummyLogger(),
    )

    # Longest column is unmapped (3 values), so we should emit 3 data rows.
    assert ws.max_row == 4  # header + 3 rows
    assert ws.max_column == 2
    assert [cell.value for cell in ws[2]] == ["a", 10]
    assert [cell.value for cell in ws[4]] == [None, 30]
