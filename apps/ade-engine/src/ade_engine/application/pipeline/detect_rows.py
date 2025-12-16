from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from ade_engine.extensions.invoke import call_extension
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import RunLogger
from ade_engine.models.errors import PipelineError
from ade_engine.models.extension_contexts import RowDetectorContext, RowKind
from ade_engine.models.extension_outputs import RowDetectorResult


@dataclass(frozen=True)
class TableRegion:
    header_row_index: int
    data_start_row_index: int
    data_end_row_index: int
    header_inferred: bool = False


def _classify_rows(
    *,
    sheet_name: str,
    rows: list[list[Any]],
    registry: Registry,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger: RunLogger,
) -> tuple[dict[int, dict[str, float]], list[str]]:
    """Run row detectors and return per-row scores and winning classification."""

    scores: dict[int, dict[str, float]] = {}
    classifications: list[str] = []
    debug = logger.isEnabledFor(logging.DEBUG)

    for row_idx, row_values in enumerate(rows):
        detectors_run: list[dict[str, Any]] = [] if debug else []
        ctx = RowDetectorContext(
            row_index=row_idx,
            row_values=row_values,
            sheet_name=sheet_name,
            metadata=metadata,
            state=state,
            input_file_name=input_file_name,
            logger=logger,
        )
        for det in registry.row_detectors:
            started = perf_counter() if debug else 0.0
            try:
                raw_patch = call_extension(det.fn, ctx, label=f"Row detector {det.qualname}")
            except Exception as exc:  # pragma: no cover - defensive
                raise PipelineError(
                    f"Row detector {det.qualname} failed on row {row_idx}"
                ) from exc

            patch = registry.validate_detector_scores(
                raw_patch,
                allow_unknown=True,
                source=f"Row detector {det.qualname}",
                model=RowDetectorResult,
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

                scores_str = ", ".join(f"{k}={v:.3f}" for k, v in rounded_patch.items())
                detector_msg = (
                    f"Row {row_idx} detector {det.qualname} on {sheet_name}"
                    + (f" (scores {scores_str})" if scores_str else "")
                )
                logger.event(
                    "detector.row_result",
                    level=logging.DEBUG,
                    message=detector_msg,
                    data={
                        "sheet_name": sheet_name,
                        "row_index": row_idx,
                        "detector": detector_payload,
                    },
                )

            if not patch:
                continue

            row_score = scores.setdefault(row_idx, {})
            for kind, delta in patch.items():
                row_score[kind] = row_score.get(kind, 0.0) + delta

        # Emit one aggregated row classification event per row (all detectors + final scores).
        row_score = scores.get(row_idx, {})
        if row_score:
            classification_type, classification_score = max(row_score.items(), key=lambda kv: kv[1])
        else:
            classification_type, classification_score = "unknown", 0.0

        if debug:
            logged_scores = {k: round(v, 6) for k, v in row_score.items()}
            logged_classification_score = round(classification_score, 6)
            considered_row_kinds = sorted(logged_scores) if logged_scores else []
            logger.event(
                "row_classification",
                level=logging.DEBUG,
                message=f"Row {row_idx} → {classification_type} ({logged_classification_score:.3f}) on {sheet_name}",
                data={
                    "sheet_name": sheet_name,
                    "row_index": row_idx,
                    "detectors": detectors_run,
                    "scores": logged_scores,
                    "classification": {
                        "row_kind": classification_type,
                        "score": logged_classification_score,
                        "considered_row_kinds": considered_row_kinds,
                    },
                },
            )

        classifications.append(classification_type)

    return scores, classifications


def _is_row_empty(row: list[Any]) -> bool:
    return not any(cell not in (None, "") for cell in row)


def _pick_best_header_row_index(
    *,
    rows: list[list[Any]],
    scores: dict[int, dict[str, float]],
    classifications: list[str],
) -> int:
    total_rows = len(classifications)
    if total_rows == 0:
        return 0

    best_index = 0
    best_score = float("-inf")
    for idx in range(total_rows):
        header_score = scores.get(idx, {}).get(RowKind.HEADER.value, 0.0)
        if header_score > best_score:
            best_score = header_score
            best_index = idx

    # If still no positive signal, choose first non-empty row.
    if best_score <= 0.0:
        for idx in range(total_rows):
            if not _is_row_empty(rows[idx]):
                return idx

    return best_index


def detect_table_regions(
    *,
    sheet_name: str,
    rows: list[list[Any]],
    registry: Registry,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger: RunLogger,
) -> list[TableRegion]:
    """Detect all table regions in a sheet.

    A table is defined as:
    - a header row (detected or inferred),
    - followed by rows until the next header (exclusive) or end of sheet.
    """

    if not rows:
        return []

    # If the sheet contains only empty rows, treat it as having no tables.
    if all(_is_row_empty(row) for row in rows):
        return []

    scores, classifications = _classify_rows(
        sheet_name=sheet_name,
        rows=rows,
        registry=registry,
        state=state,
        metadata=metadata,
        input_file_name=input_file_name,
        logger=logger,
    )

    total_rows = len(classifications)
    tables: list[TableRegion] = []

    header_idx: int | None = None
    header_inferred_from_data = False

    def close_table(*, end_idx: int) -> None:
        nonlocal header_idx, header_inferred_from_data
        if header_idx is None:
            return
        data_start_idx = min(header_idx + 1, total_rows)
        tables.append(
            TableRegion(
                header_row_index=header_idx,
                data_start_row_index=data_start_idx,
                data_end_row_index=end_idx,
                header_inferred=header_inferred_from_data,
            )
        )

    for idx, kind in enumerate(classifications):
        if header_idx is None:
            if kind == RowKind.HEADER.value:
                header_idx = idx
                header_inferred_from_data = False
            elif kind == RowKind.DATA.value and idx > 0:
                inferred_header = idx - 1
                # Avoid inferring an empty header row; fall back to treating the
                # current row as the header when the row above is empty.
                header_idx = inferred_header if not _is_row_empty(rows[inferred_header]) else idx
                header_inferred_from_data = True
            continue

        if kind == RowKind.HEADER.value and idx > header_idx:
            if header_inferred_from_data:
                # Upgrade to a concrete header and restart data tracking.
                header_idx = idx
                header_inferred_from_data = False
                continue

            close_table(end_idx=idx)
            header_idx = idx
            header_inferred_from_data = False

    if header_idx is not None:
        close_table(end_idx=total_rows)

    if not tables:
        header_idx = _pick_best_header_row_index(rows=rows, scores=scores, classifications=classifications)
        data_start_idx = min(header_idx + 1, total_rows)
        tables.append(
            TableRegion(
                header_row_index=header_idx,
                data_start_row_index=data_start_idx,
                data_end_row_index=total_rows,
                header_inferred=False,
            )
        )

    if logger.isEnabledFor(logging.DEBUG):
        sheet_index = int(metadata.get("sheet_index", 0)) if isinstance(metadata, dict) else 0
        input_file = str(metadata.get("input_file") or "") if isinstance(metadata, dict) else ""
        logger.event(
            "sheet.tables_detected",
            level=logging.DEBUG,
            data={
                "sheet_name": sheet_name,
                "sheet_index": sheet_index,
                "input_file": input_file,
                "row_count": total_rows,
                "table_count": len(tables),
                "tables": [
                    {
                        "table_index": i,
                        "region": {
                            "header_row_index": t.header_row_index,
                            "data_start_row_index": t.data_start_row_index,
                            "data_end_row_index": t.data_end_row_index,
                            "header_inferred": t.header_inferred,
                        },
                    }
                    for i, t in enumerate(tables)
                ],
            },
        )

    return tables


__all__ = ["TableRegion", "detect_table_regions"]
