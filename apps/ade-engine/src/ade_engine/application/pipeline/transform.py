from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ade_engine.extensions.invoke import call_extension
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import RunLogger
from ade_engine.models.errors import PipelineError
from ade_engine.models.extension_contexts import TransformContext
from ade_engine.models.table import TableRegion


def _normalize_transform_output(*, field_name: str, raw: Any, source: str) -> pl.Expr | None:
    if raw is None:
        return None

    if isinstance(raw, pl.Expr):
        return raw.alias(field_name)

    raise PipelineError(f"{source} must return None or a polars Expr (got {type(raw).__name__})")


def apply_transforms(
    *,
    table: pl.DataFrame,
    registry: Registry,
    settings,
    state: dict,
    metadata: dict,
    table_region: TableRegion | None = None,
    table_index: int | None = None,
    input_file_name: str | None,
    logger: RunLogger,
) -> pl.DataFrame:
    """Apply v3 transforms (Expr) to the DataFrame."""

    transforms_by_field = registry.column_transforms_by_field
    if not transforms_by_field:
        return table

    debug = logger.isEnabledFor(logging.DEBUG)

    canonical_in_table = [c for c in table.columns if c in registry.fields]
    remaining = [f for f in registry.fields.keys() if f not in canonical_in_table]
    field_order = [*canonical_in_table, *remaining]

    for field_name in field_order:
        transforms = transforms_by_field.get(field_name, [])
        if not transforms:
            continue

        if field_name not in table.columns:
            table = table.with_columns(pl.lit(None).alias(field_name))

        for tf in transforms:
            ctx = TransformContext(
                field_name=field_name,
                table=table,
                settings=settings,
                state=state,
                metadata=metadata,
                table_region=table_region,
                table_index=table_index,
                input_file_name=input_file_name,
                logger=logger,
            )

            before_sample = table.get_column(field_name).head(3).to_list() if debug else None
            raw_out = call_extension(tf.fn, ctx, label=f"Transform {tf.qualname}")
            expr = _normalize_transform_output(
                field_name=field_name,
                raw=raw_out,
                source=f"Transform {tf.qualname}",
            )
            if expr is None:
                continue

            table = table.with_columns(expr)

            if debug:
                after_sample = table.get_column(field_name).head(3).to_list()
                logger.event(
                    "transform.result",
                    level=logging.DEBUG,
                    data={
                        "transform": tf.qualname,
                        "field": field_name,
                        "table_index": table_index,
                        "table_region": table_region.ref if table_region else None,
                        "row_count": table.height,
                        "sample_before": before_sample,
                        "sample_after": after_sample,
                        "emitted_column": field_name,
                    },
                )

    return table


__all__ = ["apply_transforms"]
