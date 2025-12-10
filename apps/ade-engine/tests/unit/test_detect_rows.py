from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ade_engine.pipeline.detect_rows import detect_table_bounds
from ade_engine.registry import Registry
from ade_engine.registry.models import RowKind


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
