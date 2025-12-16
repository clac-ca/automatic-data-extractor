from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ade_engine.application.pipeline.validate import apply_validators, flatten_issues_patch
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import NullLogger
from ade_engine.models.errors import PipelineError
from ade_engine.models.extension_contexts import FieldDef
from ade_engine.models.table import MappedColumn


def _mapped_column() -> MappedColumn:
    return MappedColumn(field_name="foo", source_index=0, header="foo", values=["ok", "bad"])


def test_validator_returns_issue_list():
    registry = Registry()
    logger = NullLogger()

    def validator(*, column, **_):
        issues = []
        for idx, value in enumerate(column):
            if value == "bad":
                issues.append({"row_index": idx, "message": "bad value"})
        return issues

    registry.register_field(FieldDef(name="foo"))
    registry.register_column_validator(validator, field="foo", priority=0)
    registry.finalize()

    mapped = [_mapped_column()]
    columns = {"foo": ["ok", "bad"]}
    mapping = {"foo": 0}

    issues_patch = apply_validators(
        mapped_columns=mapped,
        columns=columns,
        mapping=mapping,
        registry=registry,
        state={},
        metadata={},
        input_file_name=None,
        logger=logger,
        row_count=2,
    )

    issues = flatten_issues_patch(issues_patch=issues_patch, columns=columns, mapping=mapping)
    assert issues == [
        {
            "field": "foo",
            "row_index": 1,
            "message": "bad value",
            "severity": None,
            "code": None,
            "meta": None,
            "value": "bad",
            "column_index": 0,
        }
    ]


def test_validator_invalid_shape_raises():
    registry = Registry()
    logger = NullLogger()

    def bad_validator(*, column, **_):
        return {"row_index": 0, "message": "oops"}

    registry.register_field(FieldDef(name="foo"))
    registry.register_column_validator(bad_validator, field="foo", priority=0)
    registry.finalize()

    mapped = [_mapped_column()]
    columns = {"foo": ["ok", "bad"]}
    mapping = {"foo": 0}

    with pytest.raises(PipelineError):
        apply_validators(
            mapped_columns=mapped,
            columns=columns,
            mapping=mapping,
            registry=registry,
            state={},
            metadata={},
            input_file_name=None,
            logger=logger,
            row_count=2,
        )
