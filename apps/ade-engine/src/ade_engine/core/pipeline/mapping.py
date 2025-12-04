"""Column mapping pipeline for converting :class:`ExtractedTable` to :class:`MappedTable`."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ade_engine.config.loader import ConfigRuntime
from ade_engine.infra.telemetry import EventEmitter
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


@dataclass(frozen=True)
class _CandidateScore:
    candidate: _ColumnCandidate
    score: float
    contributions: tuple[ScoreContribution, ...]


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
    event_emitter: EventEmitter,
) -> tuple[MappedColumn | None, list[_CandidateScore]]:
    module = runtime.columns[field]
    winning: MappedColumn | None = None
    candidate_scores: list[_CandidateScore] = []

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
                event_emitter=event_emitter,
            )

            delta = 0.0
            if isinstance(result, Mapping):
                scores_map = result.get("scores", result)
                if isinstance(scores_map, Mapping):
                    delta = float(scores_map.get(field, 0.0) or 0.0)
                else:  # fallback to numeric-like payload
                    delta = float(scores_map) if scores_map is not None else 0.0
            else:
                delta = float(result) if result is not None else 0.0
            contributions.append(
                ScoreContribution(field=field, detector=f"{module.module.__name__}.{detector.__name__}", delta=delta)
            )
            total_score += delta

        candidate_scores.append(
            _CandidateScore(candidate=candidate, score=total_score, contributions=tuple(contributions))
        )
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

    return winning, candidate_scores


def _choose_best_candidate(candidate_scores: list[_CandidateScore]) -> _CandidateScore | None:
    if not candidate_scores:
        return None
    return sorted(candidate_scores, key=lambda cs: (-cs.score, cs.candidate.index))[0]


def _candidate_payload(candidate_score: _CandidateScore | None, *, threshold: float) -> dict[str, Any] | None:
    if candidate_score is None:
        return None

    candidate = candidate_score.candidate
    return {
        "column_index": candidate.index + 1,
        "source_column_index": candidate.index,
        "header": candidate.header,
        "score": candidate_score.score,
        "passed_threshold": candidate_score.score >= threshold,
        "contributions": [
            {"detector": contribution.detector, "delta": contribution.delta}
            for contribution in candidate_score.contributions
        ],
    }


def _emit_column_score_event(
    *,
    raw: ExtractedTable,
    field: str,
    candidate_scores: list[_CandidateScore],
    winning: MappedColumn | None,
    event_emitter: EventEmitter,
    top_n: int = 3,
) -> None:
    winning_candidate = None
    if winning:
        winning_candidate = next(
            (cs for cs in candidate_scores if cs.candidate.index == winning.source_column_index),
            None,
        )

    best_candidate = _choose_best_candidate(candidate_scores)
    chosen_candidate = winning_candidate or best_candidate

    ordered = sorted(candidate_scores, key=lambda cs: (-cs.score, cs.candidate.index))
    top_candidates: list[_CandidateScore] = list(ordered[:top_n])
    for candidate in (winning_candidate, best_candidate):
        if candidate and candidate not in top_candidates:
            top_candidates.append(candidate)

    event_emitter.custom(
        "column_detector.score",
        source_file=str(raw.source_file),
        source_sheet=raw.source_sheet,
        table_index=raw.table_index,
        field=field,
        threshold=MAPPING_SCORE_THRESHOLD,
        chosen=_candidate_payload(chosen_candidate, threshold=MAPPING_SCORE_THRESHOLD),
        candidates=[_candidate_payload(candidate, threshold=MAPPING_SCORE_THRESHOLD) for candidate in top_candidates],
    )


def map_extracted_tables(
    *,
    tables: Iterable[ExtractedTable],
    runtime: ConfigRuntime,
    run: Any,
    logger: logging.Logger | None = None,
    event_emitter: EventEmitter,
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
            mapped, candidate_scores = _score_field(
                field=field,
                candidates=[c for c in candidates if c.index not in used_columns],
                runtime=runtime,
                raw=raw,
                run=run,
                logger=logger,
                state=state,
                event_emitter=event_emitter,
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
            _emit_column_score_event(
                raw=raw,
                field=field,
                candidate_scores=candidate_scores,
                winning=mapped,
                event_emitter=event_emitter,
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
