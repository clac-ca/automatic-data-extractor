"""Pure helpers for transforming raw tables into normalized structures."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from ade_engine.core.manifest import ColumnMeta
from ade_engine.core.models import JobContext
from ade_engine.core.pipeline_types import (
    ColumnModule,
    ColumnMapping,
    ExtraColumn,
    TableProcessingResult,
)

from .mapping import map_columns
from .normalize import normalize_rows


def process_table(
    *,
    job: JobContext,
    header_row: Sequence[str],
    data_rows: Sequence[Sequence[Any]],
    order: Sequence[str],
    meta: Mapping[str, Mapping[str, Any]],
    definitions: Mapping[str, ColumnMeta],
    modules: Mapping[str, ColumnModule],
    threshold: float,
    sample_size: int,
    append_unmapped: bool,
    unmapped_prefix: str,
    table_info: Mapping[str, Any],
    state: Mapping[str, Any],
    logger: logging.Logger,
) -> TableProcessingResult:
    """Return normalized rows and metadata for an in-memory table."""

    mapping, extras = map_columns(
        job,
        header_row,
        data_rows,
        order,
        meta,
        definitions,
        modules,
        threshold=threshold,
        sample_size=sample_size,
        append_unmapped=append_unmapped,
        prefix=unmapped_prefix,
        table_info=table_info,
        state=state,
        logger=logger,
    )

    normalized_rows, issues = normalize_rows(
        job,
        data_rows,
        order,
        mapping,
        extras,
        modules,
        meta,
        state=state,
        logger=logger,
    )

    return TableProcessingResult(
        mapping=list(mapping),
        extras=list(extras),
        rows=normalized_rows,
        issues=issues,
    )


__all__ = ["TableProcessingResult", "process_table"]
