from __future__ import annotations

import pytest
import polars as pl

from ade_engine.application.pipeline.transform import apply_transforms
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import NullLogger
from ade_engine.infrastructure.settings import Settings
from ade_engine.models.errors import PipelineError
from ade_engine.models.extension_contexts import FieldDef
from ade_engine.models.table import TableRegion


class SpyLogger:
    def __init__(self):
        self.events = []

    def isEnabledFor(self, _level: int) -> bool:  # noqa: N802 - match logging API
        return True

    def event(self, *args, **kwargs):
        self.events.append({"args": args, "kwargs": kwargs})


def test_transform_applies_expr_outputs():
    registry = Registry()

    def uppercase_transform(*, field_name: str, **_):
        return pl.col(field_name).cast(pl.Utf8).str.to_uppercase()

    registry.register_field(FieldDef(name="foo"))
    registry.register_column_transform(uppercase_transform, field="foo", priority=0)
    registry.finalize()

    logger = SpyLogger()
    table = pl.DataFrame({"foo": ["a", "b"]})

    out = apply_transforms(
        table=table,
        registry=registry,
        settings=Settings(),
        state={},
        metadata={},
        table_region=TableRegion(min_row=1, min_col=1, max_row=1 + table.height, max_col=max(1, table.width)),
        table_index=0,
        input_file_name="input.xlsx",
        logger=logger,
    )

    assert out.to_dict(as_series=False) == {"foo": ["A", "B"]}
    assert len(logger.events) == 1
    assert logger.events[0]["kwargs"]["data"]["row_count"] == 2


def test_transform_invalid_return_raises_pipeline_error():
    registry = Registry()

    def broken_transform(**_):
        return [1]

    registry.register_field(FieldDef(name="foo"))
    registry.register_column_transform(broken_transform, field="foo", priority=0)
    registry.finalize()

    with pytest.raises(PipelineError):
        table = pl.DataFrame({"foo": [1, 2]})
        apply_transforms(
            table=table,
            registry=registry,
            settings=Settings(),
            state={},
            metadata={},
            table_region=TableRegion(min_row=1, min_col=1, max_row=1 + table.height, max_col=max(1, table.width)),
            table_index=0,
            input_file_name="input.xlsx",
            logger=NullLogger(),
        )


def test_transform_dict_output_raises_pipeline_error():
    registry = Registry()

    def add_derived_field(*, field_name: str, **_):
        return {"bar": pl.col(field_name).cast(pl.Utf8) + pl.lit("-derived")}

    registry.register_field(FieldDef(name="foo"))
    registry.register_field(FieldDef(name="bar"))
    registry.register_column_transform(add_derived_field, field="foo", priority=10)
    registry.finalize()

    with pytest.raises(PipelineError):
        table = pl.DataFrame({"foo": ["a", "b"]})
        apply_transforms(
            table=table,
            registry=registry,
            settings=Settings(),
            state={},
            metadata={},
            table_region=TableRegion(min_row=1, min_col=1, max_row=1 + table.height, max_col=max(1, table.width)),
            table_index=0,
            input_file_name="input.xlsx",
            logger=NullLogger(),
        )
