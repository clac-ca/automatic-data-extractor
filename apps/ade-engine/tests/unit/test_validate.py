from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ade_engine.exceptions import PipelineError
from ade_engine.logging import NullLogger
from ade_engine.pipeline.models import MappedColumn
from ade_engine.pipeline.validate import apply_validators
from ade_engine.registry import FieldDef, Registry


def _mapped_column() -> MappedColumn:
    return MappedColumn(field_name="foo", source_index=0, header="foo", values=["ok", "bad"])


def test_validator_returns_issue_list():
    registry = Registry()
    logger = NullLogger()

    def validator(*, values, **_):
        issues = []
        for idx, value in enumerate(values):
            if value == "bad":
                issues.append({"row_index": idx, "message": "bad value"})
        return issues

    registry.register_field(FieldDef(name="foo"))
    registry.register_column_validator(validator, field="foo", priority=0)
    registry.finalize()

    mapped = [_mapped_column()]
    transformed_rows = [{"foo": "ok"}, {"foo": "bad"}]

    issues = apply_validators(
        mapped_columns=mapped,
        transformed_rows=transformed_rows,
        registry=registry,
        state={},
        metadata={},
        input_file_name=None,
        logger=logger,
    )

    assert issues == [
        {"field": "foo", "row_index": 1, "column_index": 0, "message": "bad value", "value": "bad"}
    ]


def test_validator_invalid_shape_raises():
    registry = Registry()
    logger = NullLogger()

    def bad_validator(*, values, **_):
        return {"row_index": 0, "message": "oops"}

    registry.register_field(FieldDef(name="foo"))
    registry.register_column_validator(bad_validator, field="foo", priority=0)
    registry.finalize()

    mapped = [_mapped_column()]
    transformed_rows = [{"foo": "ok"}, {"foo": "bad"}]

    with pytest.raises(PipelineError):
        apply_validators(
            mapped_columns=mapped,
            transformed_rows=transformed_rows,
            registry=registry,
            state={},
            metadata={},
            input_file_name=None,
            logger=logger,
        )
