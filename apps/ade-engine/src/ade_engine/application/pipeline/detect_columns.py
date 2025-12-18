from __future__ import annotations

import logging
from collections import defaultdict
from time import perf_counter
from typing import Any, Dict, List, Tuple

import polars as pl

from ade_engine.extensions.invoke import call_extension
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import RunLogger
from ade_engine.infrastructure.settings import Settings
from ade_engine.models.errors import PipelineError
from ade_engine.models.extension_contexts import ColumnDetectorContext
from ade_engine.models.extension_outputs import ColumnDetectorResult
from ade_engine.models.table import MappedColumn, SourceColumn, TableRegion


def build_source_columns(header_row: List[Any], data_rows: List[List[Any]]) -> List[SourceColumn]:
    max_cols = max((len(header_row), *(len(r) for r in data_rows)), default=0)
    cols: List[SourceColumn] = []
    for idx in range(max_cols):
        header = header_row[idx] if idx < len(header_row) else None
        values = [row[idx] if idx < len(row) else None for row in data_rows]
        cols.append(SourceColumn(index=idx, header=header, values=values))
    return cols


def _header_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()


def _build_column_sample(column: pl.Series, *, limit: int) -> list[str]:
    if limit <= 0:
        return []

    out: list[str] = []
    for value in column:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def detect_and_map_columns(
    *,
    sheet_name: str,
    table: pl.DataFrame,
    source_columns: List[SourceColumn],
    table_region: TableRegion,
    table_index: int,
    registry: Registry,
    settings: Settings,
    state: dict,
    metadata: dict,
    input_file_name: str,
    logger: RunLogger,
) -> tuple[List[MappedColumn], List[SourceColumn], dict[int, dict[str, float]], set[int]]:
    mapping_candidates: Dict[int, Tuple[str, float]] = {}
    field_competitors: Dict[str, List[Tuple[int, float]]] = defaultdict(list)
    contributions_by_column: Dict[int, Dict[str, List[Dict[str, float]]]] = {}
    scores_by_column: Dict[int, Dict[str, float]] = {}
    debug = logger.isEnabledFor(logging.DEBUG)

    for col in source_columns:
        if not (0 <= col.index < len(table.columns)):
            continue

        column_name = table.columns[col.index]
        column = table.get_column(column_name)
        column_sample = _build_column_sample(column, limit=int(settings.detectors.text_sample_size))

        scores: Dict[str, float] = {}
        contributions: Dict[str, List[Dict[str, float]]] = {} if debug else {}
        detectors_run: list[dict[str, Any]] = [] if debug else []
        ctx = ColumnDetectorContext(
            table=table,
            column=column,
            column_sample=column_sample,
            column_name=column_name,
            column_index=col.index,
            header_text=_header_text(col.header),
            settings=settings,
            sheet_name=sheet_name,
            metadata=metadata,
            state=state,
            table_region=table_region,
            table_index=table_index,
            input_file_name=input_file_name,
            logger=logger,
        )
        for det in registry.column_detectors:
            started = perf_counter() if debug else 0.0
            try:
                raw_patch = call_extension(det.fn, ctx, label=f"Column detector {det.qualname}")
            except Exception as exc:  # pragma: no cover - defensive
                raise PipelineError(
                    f"Column detector {det.qualname} failed on column {col.index}"
                ) from exc

            patch = registry.validate_detector_scores(
                raw_patch,
                allow_unknown=False,
                source=f"Column detector {det.qualname}",
                model=ColumnDetectorResult,
            )

            if debug:
                duration_ms = round((perf_counter() - started) * 1000, 5)
                rounded_patch = {k: round(v, 6) for k, v in (patch or {}).items()}

                detector_payload = {
                    "name": det.qualname,
                    "scores": rounded_patch,
                    "duration_ms": duration_ms,
                }

                detectors_run.append(detector_payload)
                logger.event(
                    "detector.column_result",
                    level=logging.DEBUG,
                    message=f"Column {col.index} detector {det.qualname} executed on {sheet_name}",
                    data={
                        "sheet_name": sheet_name,
                        "table_index": table_index,
                        "table_region": table_region.a1 if table_region else None,
                        "column_index": col.index,
                        "detector": detector_payload,
                    },
                )
            for field, delta in patch.items():
                scores[field] = scores.get(field, 0.0) + delta
                if debug:
                    contributions.setdefault(field, []).append({"detector": det.qualname, "delta": delta})

        logged_scores = {k: round(v, 6) for k, v in scores.items()} if debug else {}

        if scores:
            best_field, best_score = None, float("-inf")
            for field, score in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0])):
                if score > best_score:
                    best_field, best_score = field, score
        else:
            best_field, best_score = "unknown", 0.0

        if debug:
            considered_fields = sorted(logged_scores) if logged_scores else []

            logger.event(
                "column_classification",
                level=logging.DEBUG,
                message=f"Column {col.index} classified as {best_field} (score={best_score:.3f}) on {sheet_name}",
                data={
                    "sheet_name": sheet_name,
                    "table_index": table_index,
                    "table_region": table_region.a1 if table_region else None,
                    "column_index": col.index,
                    "detectors": detectors_run,
                    "scores": logged_scores,
                    "classification": {
                        "field": best_field,
                        "score": round(best_score, 6),
                        "considered_fields": considered_fields,
                    },
                },
            )

        if scores:
            # Keep raw (possibly negative) totals for diagnostics; consumers should
            # clamp/filter as needed for schema constraints.
            scores_by_column[col.index] = dict(scores)

        # Ignore columns with no positive signal – treating zero/negative totals as unmapped
        if not scores or best_score <= 0:
            continue
        # pick best field for this column
        if best_field is not None:
            if debug:
                logger.event(
                    "column_detector.candidate",
                    level=logging.DEBUG,
                    data={
                        "sheet_name": sheet_name,
                        "table_index": table_index,
                        "table_region": table_region.a1 if table_region else None,
                        "column_index": col.index,
                        "column_name": column_name,
                        "header_text": _header_text(col.header),
                        "best_field": best_field,
                        "best_score": best_score,
                        "scores": scores,
                        "contributions": contributions.get(best_field, []),
                    },
                )
            mapping_candidates[col.index] = (best_field, best_score)
            field_competitors[best_field].append((col.index, best_score))
            if debug:
                contributions_by_column[col.index] = contributions

    # resolve duplicates across columns mapping to same field
    unmapped_indices: set[int] = set()
    for field, entries in field_competitors.items():
        if len(entries) == 1:
            continue
        # Highest score wins; fall back to leftmost only when scores tie
        entries_sorted = sorted(entries, key=lambda e: (-e[1], e[0]))
        if settings.mapping_tie_resolution == "leftmost":
            # keep the best-scoring column, drop the rest
            for col_idx, _ in entries_sorted[1:]:
                unmapped_indices.add(col_idx)
        else:  # leave_unmapped
            for col_idx, _ in entries_sorted:
                unmapped_indices.add(col_idx)

    mapped_cols: List[MappedColumn] = []
    for col in source_columns:
        candidate = mapping_candidates.get(col.index)
        if not candidate or col.index in unmapped_indices:
            continue
        field_name, score = candidate
        mapped_cols.append(
            MappedColumn(
                field_name=field_name,
                source_index=col.index,
                header=col.header,
                values=col.values,
                score=score,
            )
        )

    # unmapped columns: those not in mapped_cols or dropped due to tie or without scores
    mapped_indices = {c.source_index for c in mapped_cols}
    unmapped = [c for c in source_columns if c.index not in mapped_indices]

    # Preserve deterministic ordering
    mapped_cols.sort(key=lambda c: c.source_index)
    unmapped.sort(key=lambda c: c.index)

    if debug:
        logger.event(
            "column_detector.summary",
            level=logging.DEBUG,
            data={
                "mapped": [
                    {
                        "field": m.field_name,
                        "source_index": m.source_index,
                        "header": m.header,
                        "score": m.score,
                        "contributions": contributions_by_column.get(m.source_index, {}).get(m.field_name, []),
                    }
                    for m in mapped_cols
                ],
                "unmapped_indices": sorted(unmapped_indices),
                "total_columns": len(source_columns),
            },
        )

    return mapped_cols, unmapped, scores_by_column, unmapped_indices


__all__ = ["detect_and_map_columns", "build_source_columns"]
