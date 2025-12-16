from __future__ import annotations

from openpyxl import Workbook

from ade_engine.application.pipeline.pipeline import Pipeline
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import NullLogger
from ade_engine.infrastructure.settings import Settings
from ade_engine.models.extension_contexts import RowKind


def test_process_sheet_renders_multiple_tables_with_blank_row():
    registry = Registry()
    logger = NullLogger()

    def detector(*, row_index, **_):
        if row_index in (0, 3):
            return {RowKind.HEADER.value: 1.0}
        if row_index in (1, 2, 4):
            return {RowKind.DATA.value: 1.0}
        return {}

    registry.register_row_detector(detector, row_kind=RowKind.UNKNOWN.value, priority=0)
    registry.finalize()

    pipeline = Pipeline(registry=registry, settings=Settings(), logger=logger)

    source_wb = Workbook()
    source_ws = source_wb.active
    source_ws.title = "Sheet1"
    source_ws.append(["A", "B"])
    source_ws.append([1, 2])
    source_ws.append([3, 4])
    source_ws.append(["C", "D"])
    source_ws.append([5, 6])

    output_wb = Workbook()
    output_wb.remove(output_wb.active)
    output_ws = output_wb.create_sheet(title="Sheet1")

    tables = pipeline.process_sheet(
        sheet=source_ws,
        output_sheet=output_ws,
        state={},
        metadata={"input_file": "input.xlsx", "sheet_index": 0},
        input_file_name="input.xlsx",
    )

    assert [t.table_index for t in tables] == [0, 1]

    emitted = list(output_ws.iter_rows(min_row=1, max_row=6, max_col=2, values_only=True))
    assert emitted == [
        ("raw_A", "raw_B"),
        (1, 2),
        (3, 4),
        (None, None),  # blank separator row
        ("raw_C", "raw_D"),
        (5, 6),
    ]
