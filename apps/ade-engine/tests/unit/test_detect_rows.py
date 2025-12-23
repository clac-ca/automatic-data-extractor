from __future__ import annotations

import pytest

from ade_engine.application.pipeline.detect_rows import _classify_rows, detect_table_regions
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import NullLogger
from ade_engine.infrastructure.settings import Settings
from ade_engine.models.errors import PipelineError
from ade_engine.models.extension_contexts import RowKind


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
        settings=Settings(),
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
            settings=Settings(),
            state={},
            metadata={},
            input_file_name=None,
            logger=logger,
        )


def test_detect_table_regions_merges_contiguous_header_rows_by_default():
    reg = Registry()
    logger = NullLogger()

    def detector(*, row_index, **_):
        if row_index in (1, 2):
            return {RowKind.HEADER.value: 1.0}
        if row_index == 3:
            return {RowKind.DATA.value: 1.0}
        return {}

    reg.register_row_detector(detector, row_kind=RowKind.UNKNOWN.value, priority=0)

    tables = detect_table_regions(
        sheet_name="Sheet1",
        rows=[
            ["H1", "A"],
            ["H2", "B"],
            ["v1", "v2"],
        ],
        registry=reg,
        settings=Settings(),
        state={},
        metadata={"input_file": "input.xlsx", "sheet_index": 0},
        input_file_name=None,
        logger=logger,
    )

    assert [(t.min_row, t.max_row, t.max_col, t.header_row_count) for t in tables] == [
        (1, 3, 2, 2),
    ]


def test_detect_table_regions_can_disable_header_merge():
    reg = Registry()
    logger = NullLogger()

    def detector(*, row_index, **_):
        if row_index in (1, 2):
            return {RowKind.HEADER.value: 1.0}
        if row_index == 3:
            return {RowKind.DATA.value: 1.0}
        return {}

    reg.register_row_detector(detector, row_kind=RowKind.UNKNOWN.value, priority=0)

    tables = detect_table_regions(
        sheet_name="Sheet1",
        rows=[
            ["H1", "A"],
            ["H2", "B"],
            ["v1", "v2"],
        ],
        registry=reg,
        settings=Settings(merge_stacked_headers=False),
        state={},
        metadata={"input_file": "input.xlsx", "sheet_index": 0},
        input_file_name=None,
        logger=logger,
    )

    assert [(t.min_row, t.max_row, t.max_col) for t in tables] == [
        (1, 1, 2),
        (2, 3, 2),
    ]


def test_detect_table_regions_returns_multiple_tables():
    reg = Registry()
    logger = NullLogger()

    def detector(*, row_index, **_):
        if row_index in (1, 4):
            return {RowKind.HEADER.value: 1.0}
        if row_index in (2, 3, 5):
            return {RowKind.DATA.value: 1.0}
        return {}

    reg.register_row_detector(detector, row_kind=RowKind.UNKNOWN.value, priority=0)

    tables = detect_table_regions(
        sheet_name="Sheet1",
        rows=[
            ["H1", "A"],
            ["v1", "v2"],
            ["v3", "v4"],
            ["H2", "B"],
            ["v5", "v6"],
        ],
        registry=reg,
        settings=Settings(),
        state={},
        metadata={"input_file": "input.xlsx", "sheet_index": 0},
        input_file_name="input.xlsx",
        logger=logger,
    )

    assert [(t.min_row, t.max_row, t.max_col) for t in tables] == [
        (1, 3, 2),
        (4, 5, 2),
    ]
