"""Column mapping pipeline for converting :class:`ExtractedTable` to :class:`MappedTable`."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from ade_engine.config.loader import ConfigRuntime
from ade_engine.core.types import (
    ColumnMap,
    MappedColumn,
    MappedTable,
    ExtractedTable,
    ScoreContribution,
    UnmappedColumn,
)


# Threshold for accepting a column mapping candidate.
MAPPING_SCORE_THRESHOLD = 0.5

# Number of sample values forwarded to column detectors for quick inspection.
COLUMN_SAMPLE_SIZE = 10


@dataclass
class _ColumnCandidate:
    index: int
    header: str
    values: list[Any]


def _collect_columns(raw: ExtractedTable) -> list[_ColumnCandidate]:
    max_columns = max(
        [len(raw.header_row)] + [len(row) for row in raw.data_rows] if raw.data_rows else [len(raw.header_row)]
    )

    candidates: list[_ColumnCandidate] = []
    for idx in range(max_columns):
        header = raw.header_row[idx] if idx < len(raw.header_row) else ""
        values = [row[idx] if idx < len(row) else None for row in raw.data_rows]
        candidates.append(_ColumnCandidate(index=idx, header=header, values=values))

    return candidates


def _score_field(
    *,
    field: str,
    candidates: Iterable[_ColumnCandidate],
    runtime: ConfigRuntime,
    raw: ExtractedTable,
    run: Any,
    logger: logging.Logger,
    state: dict[str, Any],
) -> tuple[MappedColumn | None, dict[int, float]]:
    module = runtime.columns[field]
    column_scores: dict[int, float] = {}
    winning: MappedColumn | None = None

    for candidate in candidates:
        contributions: list[ScoreContribution] = []
        total_score = 0.0
        for detector in module.detectors:
            result = detector(
                run=run,
                state=state,
                raw_table=raw,
                column_index=candidate.index + 1,  # script API is 1-based
                header=candidate.header,
                column_values=candidate.values,
                column_values_sample=candidate.values[:COLUMN_SAMPLE_SIZE],
                manifest=runtime.manifest,
                logger=logger,
            )
            delta = float(result) if result is not None else 0.0
            contributions.append(
                ScoreContribution(field=field, detector=f"{module.module.__name__}.{detector.__name__}", delta=delta)
            )
            total_score += delta

        column_scores[candidate.index] = total_score
        if total_score >= MAPPING_SCORE_THRESHOLD:
            mapped = MappedColumn(
                field=field,
                header=candidate.header,
                source_column_index=candidate.index,
                score=total_score,
                contributions=tuple(contributions),
                is_required=module.definition.required,
                is_satisfied=True,
            )
            if winning is None or mapped.score > winning.score or (
                mapped.score == winning.score and mapped.source_column_index < winning.source_column_index
            ):
                winning = mapped

    return winning, column_scores


def map_extracted_tables(
    *,
    tables: Iterable[ExtractedTable],
    runtime: ConfigRuntime,
    run: Any,
    logger: logging.Logger | None = None,
) -> list[MappedTable]:
    """Map physical columns in :class:`ExtractedTable` objects to manifest fields."""

    logger = logger or logging.getLogger(__name__)
    mapped_tables: list[MappedTable] = []
    state: dict[str, Any] = {}

    for raw in tables:
        candidates = _collect_columns(raw)
        used_columns: set[int] = set()
        mapped_columns: list[MappedColumn] = []

        for field in runtime.manifest.columns.order:
            mapped, scores = _score_field(
                field=field,
                candidates=[c for c in candidates if c.index not in used_columns],
                runtime=runtime,
                raw=raw,
                run=run,
                logger=logger,
                state=state,
            )
            if mapped:
                mapped_columns.append(mapped)
                used_columns.add(mapped.source_column_index)
            else:
                mapped_columns.append(
                    MappedColumn(
                        field=field,
                        header="",
                        source_column_index=-1,
                        score=0.0,
                        contributions=(),
                        is_required=runtime.manifest.columns.fields[field].required,
                        is_satisfied=False,
                    )
                )

        unmapped_columns = [
            UnmappedColumn(
                header=c.header,
                source_column_index=c.index,
                output_header=f"{runtime.manifest.writer.unmapped_prefix}{c.index + 1}",
            )
            for c in candidates
            if c.index not in used_columns
        ]

        column_map = ColumnMap(mapped_columns=mapped_columns, unmapped_columns=unmapped_columns)
        mapped_tables.append(MappedTable(extracted=raw, column_map=column_map))

    return mapped_tables


__all__ = ["map_extracted_tables", "MAPPING_SCORE_THRESHOLD", "COLUMN_SAMPLE_SIZE"]
