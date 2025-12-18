from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ade_engine.extensions.invoke import call_extension
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import RunLogger
from ade_engine.models.errors import PipelineError
from ade_engine.models.extension_contexts import TransformContext


def _normalize_transform_output(*, field_name: str, raw: Any, source: str) -> list[pl.Expr]:
    if raw is None:
        return []

    if isinstance(raw, pl.Expr):
        return [raw.alias(field_name)]

    if isinstance(raw, dict):
        exprs: list[pl.Expr] = []
        for out_name, expr in raw.items():
            if not isinstance(out_name, str) or not out_name.strip():
                raise PipelineError(f"{source} output column names must be non-empty strings")
            if not isinstance(expr, pl.Expr):
                raise PipelineError(
                    f"{source} output for '{out_name}' must be a polars Expr (got {type(expr).__name__})"
                )
            exprs.append(expr.alias(out_name))
        return exprs

    raise PipelineError(
        f"{source} must return None, a polars Expr, or a dict[str, polars Expr] (got {type(raw).__name__})"
    )


def apply_transforms(
    *,
    table: pl.DataFrame,
    registry: Registry,
    settings,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger: RunLogger,
) -> pl.DataFrame:
    """Apply v3 transforms (Expr / dict[str, Expr]) to the DataFrame."""

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
                input_file_name=input_file_name,
                logger=logger,
            )

            before_sample = table.get_column(field_name).head(3).to_list() if debug else None
            raw_out = call_extension(tf.fn, ctx, label=f"Transform {tf.qualname}")
            exprs = _normalize_transform_output(
                field_name=field_name,
                raw=raw_out,
                source=f"Transform {tf.qualname}",
            )
            if not exprs:
                continue

            table = table.with_columns(exprs)

            if debug:
                after_sample = table.get_column(field_name).head(3).to_list()
                emitted = [e.meta.output_name() or "<expr>" for e in exprs]
                logger.event(
                    "transform.result",
                    level=logging.DEBUG,
                    data={
                        "transform": tf.qualname,
                        "field": field_name,
                        "row_count": table.height,
                        "sample_before": before_sample,
                        "sample_after": after_sample,
                        "emitted_columns": emitted,
                    },
                )

    return table


__all__ = ["apply_transforms"]
