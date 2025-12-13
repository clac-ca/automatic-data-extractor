from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ade_engine.exceptions import PipelineError
from ade_engine.logging import NullLogger
from ade_engine.pipeline.detect_rows import _classify_rows, detect_table_bounds
from ade_engine.registry import Registry
from ade_engine.registry.models import RowKind


def test_row_detector_registration_normalizes_enum_row_kind_for_mapping_patch():
    reg = Registry()
    logger = NullLogger()

    def pick_header(*, row_index, **_):
        return {RowKind.HEADER.value: 1.0}

    reg.register_row_detector(pick_header, row_kind=RowKind.HEADER.value, priority=5)

    scores, classifications = _classify_rows(
        sheet_name="Sheet1",
        rows=[["H1"]],
        registry=reg,
        state={},
        metadata={},
        input_file_name=None,
        logger=logger,
    )

    assert reg.row_detectors[0].row_kind == RowKind.HEADER.value
    assert classifications == [RowKind.HEADER.value]
    assert scores[0][RowKind.HEADER.value] == 1.0


def test_row_detector_invalid_return_shape_raises():
    reg = Registry()
    logger = NullLogger()

    def pick_header(*, row_index, **_):
        return 1.0

    reg.register_row_detector(pick_header, row_kind=RowKind.HEADER.value, priority=5)

    with pytest.raises(PipelineError):
        _classify_rows(
            sheet_name="Sheet1",
            rows=[["H1"]],
            registry=reg,
            state={},
            metadata={},
            input_file_name=None,
            logger=logger,
        )


def test_detect_table_bounds_stops_at_next_header_without_data():
    reg = Registry()
    logger = NullLogger()

    def detector(*, row_index, **_):
        if row_index in (0, 1):
            return {RowKind.HEADER.value: 1.0}
        if row_index == 2:
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
        metadata={},
        input_file_name=None,
        logger=logger,
    )

    assert header_idx == 0
    assert data_start_idx == 1  # header row + 1
    assert data_end_idx == 1  # stop at the next header even without intervening data
