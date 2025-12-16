from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ade_engine.application.pipeline.transform import apply_transforms
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import NullLogger
from ade_engine.infrastructure.settings import Settings
from ade_engine.models.errors import PipelineError
from ade_engine.models.extension_contexts import FieldDef
from ade_engine.models.table import MappedColumn


class SpyLogger:
    def __init__(self):
        self.events = []

    def isEnabledFor(self, _level: int) -> bool:  # noqa: N802 - match logging API
        return True

    def event(self, *args, **kwargs):
        self.events.append({"args": args, "kwargs": kwargs})


def test_transform_applies_row_outputs_and_enforces_contract():
    registry = Registry()

    def uppercase_transform(*, column, **_):
        return [str(value).upper() if value is not None else None for value in column]

    registry.register_field(FieldDef(name="foo"))
    registry.register_column_transform(uppercase_transform, field="foo", priority=0)
    registry.finalize()

    mapped = [MappedColumn(field_name="foo", source_index=0, header="foo", values=["a", "b"])]
    logger = SpyLogger()

    columns = {"foo": ["a", "b"]}
    mapping = {"foo": 0}
    patch = apply_transforms(
        mapped_columns=mapped,
        columns=columns,
        mapping=mapping,
        registry=registry,
        settings=Settings(),
        state={},
        metadata={},
        input_file_name=None,
        logger=logger,
        row_count=2,
    )

    assert columns == {"foo": ["A", "B"]}
    assert patch.issues == {}
    assert len(logger.events) == 1
    assert logger.events[0]["kwargs"]["data"]["row_count"] == 2


def test_transform_invalid_return_raises_pipeline_error():
    registry = Registry()
    logger = NullLogger()

    def broken_transform(*, column, **_):
        return column[:1]

    registry.register_field(FieldDef(name="foo"))
    registry.register_column_transform(broken_transform, field="foo", priority=0)
    registry.finalize()

    mapped = [MappedColumn(field_name="foo", source_index=0, header="foo", values=[1, 2])]
    columns = {"foo": [1, 2]}
    mapping = {"foo": 0}

    with pytest.raises(PipelineError):
        apply_transforms(
            mapped_columns=mapped,
            columns=columns,
            mapping=mapping,
            registry=registry,
            settings=Settings(),
            state={},
            metadata={},
            input_file_name=None,
            logger=logger,
            row_count=2,
        )


def test_transform_chain_passes_scalar_values_and_accumulates_patches():
    registry = Registry()

    def add_derived_field(*, column, **_):
        return {"bar": [f"{value}-derived" if value is not None else None for value in column]}

    def uppercase_transform(*, column, **_):
        return [str(value).upper() if value is not None else None for value in column]

    registry.register_field(FieldDef(name="foo"))
    registry.register_field(FieldDef(name="bar"))
    registry.register_column_transform(add_derived_field, field="foo", priority=10)
    registry.register_column_transform(uppercase_transform, field="foo", priority=0)
    registry.finalize()

    mapped = [MappedColumn(field_name="foo", source_index=0, header="foo", values=["a", "b"])]
    columns = {"foo": ["a", "b"]}
    mapping = {"foo": 0}

    apply_transforms(
        mapped_columns=mapped,
        columns=columns,
        mapping=mapping,
        registry=registry,
        settings=Settings(),
        state={},
        metadata={},
        input_file_name=None,
        logger=NullLogger(),
        row_count=2,
    )

    assert columns == {"foo": ["A", "B"], "bar": ["a-derived", "b-derived"]}
