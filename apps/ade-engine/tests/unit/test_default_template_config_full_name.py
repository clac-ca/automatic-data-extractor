from __future__ import annotations

from pathlib import Path

import polars as pl

from ade_engine.application.pipeline.transform import apply_transforms
from ade_engine.extensions.loader import import_and_register
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import NullLogger
from ade_engine.infrastructure.settings import Settings


def test_default_template_full_name_transform_normalizes_common_formats():
    template_dir = (
        Path(__file__).resolve().parents[2]
        / "src/ade_engine/extensions/templates/config_packages/default"
    )

    registry = Registry()
    import_and_register(template_dir, registry=registry)
    registry.finalize()

    out = apply_transforms(
        table=pl.DataFrame({"full_name": ["Doe, John", "Jane Doe", "Cher", None]}),
        registry=registry,
        settings=Settings(),
        state={},
        metadata={},
        input_file_name=None,
        logger=NullLogger(),
    )

    assert out.columns == ["full_name"]
    assert out["full_name"].to_list() == ["John Doe", "Jane Doe", "Cher", None]
