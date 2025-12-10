from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ade_engine.exceptions import PipelineError
from ade_engine.pipeline.models import MappedColumn
from ade_engine.pipeline.transform import apply_transforms
from ade_engine.registry import FieldDef, Registry


class SpyLogger:
    def __init__(self):
        self.events = []

    def event(self, *args, **kwargs):
        self.events.append({"args": args, "kwargs": kwargs})


def test_transform_applies_row_outputs_and_enforces_contract():
    registry = Registry()

    def uppercase_transform(*, values, **_):
        return [
            {"row_index": idx, "value": {"foo": str(value).upper() if value is not None else None}}
            for idx, value in enumerate(values)
        ]

    registry.register_field(FieldDef(name="foo"))
    registry.register_column_transform(uppercase_transform, field="foo", priority=0)
    registry.finalize()

    mapped = [MappedColumn(field_name="foo", source_index=0, header="foo", values=["a", "b"])]
    logger = SpyLogger()

    result = apply_transforms(
        mapped_columns=mapped,
        registry=registry,
        state={},
        metadata={},
        input_file_name=None,
        logger=logger,
    )

    assert result == [{"foo": "A"}, {"foo": "B"}]
    assert len(logger.events) == 1
    assert logger.events[0]["kwargs"]["data"]["output_len"] == 2


def test_transform_invalid_return_raises_pipeline_error():
    registry = Registry()

    def broken_transform(*, values, **_):
        return None

    registry.register_field(FieldDef(name="foo"))
    registry.register_column_transform(broken_transform, field="foo", priority=0)
    registry.finalize()

    mapped = [MappedColumn(field_name="foo", source_index=0, header="foo", values=[1, 2])]

    with pytest.raises(PipelineError):
        apply_transforms(
            mapped_columns=mapped,
            registry=registry,
            state={},
            metadata={},
            input_file_name=None,
            logger=None,
        )
