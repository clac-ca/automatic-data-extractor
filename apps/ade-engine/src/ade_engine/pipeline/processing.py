"""Pure helpers for transforming raw tables into normalized structures."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ade_schemas.manifest import ColumnMeta

from ..model import JobContext
from .mapping import map_columns
from .models import ColumnModule, ColumnMapping, ExtraColumn
from .normalize import normalize_rows


@dataclass(slots=True)
class TableProcessingResult:
    """Normalized view of a single table after mapping and validation."""

    mapping: list[ColumnMapping]
    extras: list[ExtraColumn]
    rows: list[list[Any]]
    issues: list[dict[str, Any]]


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

