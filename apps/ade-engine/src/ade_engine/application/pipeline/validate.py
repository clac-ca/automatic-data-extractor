from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ade_engine.extensions.invoke import call_extension
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import RunLogger
from ade_engine.models.errors import PipelineError
from ade_engine.models.extension_contexts import ValidateContext

_ISSUE_PREFIX = "__ade_issue__"
_HAS_ISSUES_COL = "__ade_has_issues"
_ISSUE_COUNT_COL = "__ade_issue_count"


def _normalize_validator_output(*, raw: Any, source: str) -> pl.Expr | None:
    if raw is None:
        return None
    if isinstance(raw, pl.Expr):
        return raw
    raise PipelineError(
        f"{source} must return None or a polars Expr (got {type(raw).__name__})"
    )


def _combine_issue_messages(existing: pl.Expr | None, new: pl.Expr) -> pl.Expr:
    existing_str = existing.cast(pl.Utf8) if existing is not None else None
    new_str = new.cast(pl.Utf8)
    if existing_str is None:
        return new_str

    return (
        pl.when(existing_str.is_null())
        .then(new_str)
        .otherwise(
            pl.when(new_str.is_null())
            .then(existing_str)
            .otherwise(pl.concat_str([existing_str, new_str], separator="; "))
        )
    )


def apply_validators(
    *,
    table: pl.DataFrame,
    registry: Registry,
    settings,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger: RunLogger,
) -> pl.DataFrame:
    """Apply v3 validators (issue-message Expr) inline to the DataFrame."""

    validators_by_field = registry.column_validators_by_field
    debug = logger.isEnabledFor(logging.DEBUG)

    canonical_in_table = [c for c in table.columns if c in registry.fields]
    remaining = [f for f in registry.fields.keys() if f not in canonical_in_table]
    field_order = [*canonical_in_table, *remaining]

    issue_columns: list[str] = []

    for field_name in field_order:
        validators = validators_by_field.get(field_name, [])
        if not validators:
            continue

        if field_name not in table.columns:
            table = table.with_columns(pl.lit(None).alias(field_name))

        combined: pl.Expr | None = None
        for val in validators:
            ctx = ValidateContext(
                field_name=field_name,
                table=table,
                settings=settings,
                state=state,
                metadata=metadata,
                input_file_name=input_file_name,
                logger=logger,
            )
            raw = call_extension(val.fn, ctx, label=f"Validator {val.qualname}")
            expr = _normalize_validator_output(raw=raw, source=f"Validator {val.qualname}")
            if expr is None:
                continue
            combined = _combine_issue_messages(combined, expr)

        if combined is None:
            continue

        issue_col = f"{_ISSUE_PREFIX}{field_name}"
        issue_columns.append(issue_col)
        table = table.with_columns(combined.alias(issue_col))

    if issue_columns:
        has_expr = pl.any_horizontal([pl.col(c).is_not_null() for c in issue_columns])
        count_expr = pl.sum_horizontal([pl.col(c).is_not_null().cast(pl.Int32) for c in issue_columns])
    else:
        has_expr = pl.lit(False)
        count_expr = pl.lit(0, dtype=pl.Int32)

    table = table.with_columns(
        [
            has_expr.alias(_HAS_ISSUES_COL),
            count_expr.alias(_ISSUE_COUNT_COL),
        ]
    )

    if debug:
        logger.event(
            "validation.summary",
            level=logging.DEBUG,
            data={
                "issue_columns": issue_columns,
                "rows": table.height,
            },
        )

    return table


__all__ = ["apply_validators"]
