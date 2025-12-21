from __future__ import annotations

import polars as pl
import pytest
from openpyxl import Workbook

from ade_engine.application.pipeline.pipeline import _apply_mapping_as_rename, _normalize_headers
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import NullLogger
from ade_engine.infrastructure.settings import Settings
from ade_engine.models.errors import HookError
from ade_engine.models.extension_contexts import FieldDef, HookName
from ade_engine.models.table import TableRegion


class WarningSpyLogger:
    def __init__(self) -> None:
        self.warnings: list[dict] = []

    def warning(self, _msg: str, *, extra=None, **_kwargs) -> None:
        self.warnings.append({"extra": extra})


def test_header_normalization_is_deterministic_and_unique():
    headers = [None, "", "A", "A", "  A  ", 123, ""]
    assert _normalize_headers(headers, start_index=1) == [
        "col_1",
        "col_2",
        "A",
        "A__2",
        "A__3",
        "123",
        "col_7",
    ]


def test_mapping_as_rename_skips_collisions():
    table = pl.DataFrame({"Email": ["a"], "email": ["already"]})
    logger = WarningSpyLogger()
    out, rename_map = _apply_mapping_as_rename(
        table=table,
        mapped_source_indices=[0],
        mapped_field_names=["email"],
        extracted_names_by_index=["Email", "email"],
        sheet_name="Sheet1",
        table_index=0,
        logger=logger,
    )

    assert out.columns == ["Email", "email"]
    assert rename_map == {}
    assert len(logger.warnings) == 1


def test_table_hooks_compose_returned_dataframes():
    registry = Registry()
    registry.register_field(FieldDef(name="email"))

    def add_col(*, table: pl.DataFrame, **_):
        return table.with_columns(pl.lit(1).alias("x"))

    def bump_col(*, table: pl.DataFrame, **_):
        assert "x" in table.columns
        return table.with_columns((pl.col("x") + 1).alias("x"))

    registry.register_hook(add_col, hook="on_table_mapped", priority=10)
    registry.register_hook(bump_col, hook="on_table_mapped", priority=0)
    registry.finalize()

    wb = Workbook()
    ws = wb.active
    table_region = TableRegion(min_row=1, min_col=1, max_row=2, max_col=1)

    out = registry.run_hooks(
        HookName.ON_TABLE_MAPPED,
        settings=Settings(),
        state={},
        metadata={},
        logger=NullLogger(),
        input_file_name="input.xlsx",
        source_workbook=wb,
        source_sheet=ws,
        table=pl.DataFrame({"email": ["a@example.com"]}),
        source_region=table_region,
        table_index=0,
    )
    assert out is not None
    assert out.to_dict(as_series=False) == {"email": ["a@example.com"], "x": [2]}


def test_table_hook_return_type_is_enforced():
    registry = Registry()
    registry.register_field(FieldDef(name="email"))

    def bad_hook(**_):
        return 123

    registry.register_hook(bad_hook, hook="on_table_mapped", priority=0)
    registry.finalize()

    wb = Workbook()
    ws = wb.active
    table_region = TableRegion(min_row=1, min_col=1, max_row=2, max_col=1)

    with pytest.raises(HookError):
        registry.run_hooks(
            HookName.ON_TABLE_MAPPED,
            settings=Settings(),
            state={},
            metadata={},
            logger=NullLogger(),
            input_file_name="input.xlsx",
            source_workbook=wb,
            source_sheet=ws,
            table=pl.DataFrame({"email": ["a@example.com"]}),
            source_region=table_region,
            table_index=0,
        )
