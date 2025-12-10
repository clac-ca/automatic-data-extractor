from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ade_engine.pipeline.models import MappedColumn
from ade_engine.pipeline.transform import apply_transforms
from ade_engine.registry import Registry


class SpyLogger:
    def __init__(self):
        self.exceptions = []
        self.events = []

    def exception(self, msg, *args, **kwargs):
        self.exceptions.append({"msg": msg, "args": args, "kwargs": kwargs})

    def event(self, *args, **kwargs):
        self.events.append({"args": args, "kwargs": kwargs})


def test_transform_returning_none_falls_back_to_existing_values():
    registry = Registry()

    def broken_transform(ctx):
        return None

    registry.register_column_transform(broken_transform, field="foo", priority=0)
    registry.finalize()

    mapped = [MappedColumn(field_name="foo", source_index=0, header="foo", values=[1, 2])]
    logger = SpyLogger()

    result = apply_transforms(
        mapped_columns=mapped,
        registry=registry,
        state={},
        run_metadata={},
        logger=logger,
    )

    assert result == [{"foo": 1}, {"foo": 2}]
    assert len(logger.exceptions) == 1
    assert "Transform failed" in logger.exceptions[0]["msg"]
