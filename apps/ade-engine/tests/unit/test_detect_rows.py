from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ade_engine.pipeline.detect_rows import _classify_rows, detect_table_bounds
from ade_engine.registry import Registry, registry_context, row_detector
from ade_engine.registry.models import RowKind


def test_row_detector_decorator_normalizes_enum_row_kind_for_numeric_patch():
    reg = Registry()

    with registry_context(reg):
        @row_detector(row_kind=RowKind.HEADER, priority=5)
        def pick_header(ctx):
            return 1.0

    scores, classifications = _classify_rows(
        sheet_name="Sheet1",
        rows=[["H1"]],
        registry=reg,
        state={},
        run_metadata={},
        logger=None,
    )

    assert reg.row_detectors[0].row_kind == RowKind.HEADER.value
    assert classifications == [RowKind.HEADER.value]
    assert scores[0][RowKind.HEADER.value] == 1.0


def test_detect_table_bounds_stops_at_next_header_without_data():
    reg = Registry()

    def detector(ctx):
        if ctx.row_index in (0, 1):
            return {RowKind.HEADER.value: 1.0}
        if ctx.row_index == 2:
            return {RowKind.DATA.value: 1.0}
        return {}

    reg.register_row_detector(detector, row_kind=RowKind.UNKNOWN.value, priority=0)

    header_idx, data_start_idx, data_end_idx = detect_table_bounds(
        sheet_name="Sheet1",
        rows=[
            ["H1", "A"],
            ["H2", "B"],
            ["v1", "v2"],
        ],
        registry=reg,
        state={},
        run_metadata={},
        logger=None,
    )

    assert header_idx == 0
    assert data_start_idx == 1  # header row + 1
    assert data_end_idx == 1  # stop at the next header even without intervening data
