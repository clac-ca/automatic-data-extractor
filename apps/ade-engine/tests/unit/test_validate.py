from __future__ import annotations

import pytest
import polars as pl

from ade_engine.application.pipeline.validate import apply_validators
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import NullLogger
from ade_engine.infrastructure.settings import Settings
from ade_engine.models.errors import PipelineError
from ade_engine.models.extension_contexts import FieldDef
from ade_engine.models.table import TableRegion


def test_validator_writes_inline_issue_columns():
    registry = Registry()

    def validator(*, field_name: str, **_):
        v = pl.col(field_name).cast(pl.Utf8)
        return (
            pl.when(v == "bad")
            .then(pl.lit("bad value"))
            .otherwise(pl.lit(None))
        )

    registry.register_field(FieldDef(name="foo"))
    registry.register_column_validator(validator, field="foo", priority=0)
    registry.finalize()

    table = pl.DataFrame({"foo": ["ok", "bad"]})
    out = apply_validators(
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

    assert out.select(
        ["__ade_issue__foo", "__ade_has_issues", "__ade_issue_count"]
    ).to_dict(as_series=False) == {
        "__ade_issue__foo": [None, "bad value"],
        "__ade_has_issues": [False, True],
        "__ade_issue_count": [0, 1],
    }


def test_validator_invalid_return_raises():
    registry = Registry()

    def bad_validator(**_):
        return {"row_index": 0, "message": "oops"}

    registry.register_field(FieldDef(name="foo"))
    registry.register_column_validator(bad_validator, field="foo", priority=0)
    registry.finalize()

    with pytest.raises(PipelineError):
        table = pl.DataFrame({"foo": ["ok", "bad"]})
        apply_validators(
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


def test_inline_issues_stay_aligned_after_filter():
    registry = Registry()

    def validator(*, field_name: str, **_):
        return (
            pl.when(pl.col(field_name) == 2)
            .then(pl.lit("bad id"))
            .otherwise(pl.lit(None))
        )

    registry.register_field(FieldDef(name="id"))
    registry.register_column_validator(validator, field="id", priority=0)
    registry.finalize()

    table = pl.DataFrame({"id": [1, 2, 3]})
    out = apply_validators(
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

    filtered = out.filter(pl.col("id") == 2)
    assert filtered.to_dict(as_series=False) == {
        "id": [2],
        "__ade_issue__id": ["bad id"],
        "__ade_has_issues": [True],
        "__ade_issue_count": [1],
    }
