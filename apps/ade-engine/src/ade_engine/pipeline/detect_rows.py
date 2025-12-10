from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Dict, List, Tuple

from ade_engine.registry.models import RowDetectorContext, RowKind
from ade_engine.registry.registry import Registry
from ade_engine.logging import RunLogger


def _classify_rows(
    *,
    sheet_name: str,
    rows: List[List[Any]],
    registry: Registry,
    state: dict,
    run_metadata: dict,
    logger: RunLogger,
) -> Tuple[Dict[int, Dict[str, float]], List[str]]:
    """Run row detectors and return per-row scores and winning classification."""

    scores: Dict[int, Dict[str, float]] = {}
    classifications: List[str] = []
    for row_idx, row_values in enumerate(rows):
        detectors_run: list[dict[str, Any]] = []
        ctx = RowDetectorContext(
            row_index=row_idx,
            row_values=row_values,
            sheet_name=sheet_name,
            run_metadata=run_metadata,
            state=state,
            logger=logger,
        )
        for det in registry.row_detectors:
            started = perf_counter()
            try:
                patch = registry.normalize_patch(det.row_kind or RowKind.UNKNOWN.value, det.fn(ctx), allow_unknown=True)
            except Exception:
                if logger:
                    logger.exception("Row detector failed", extra={"data": {"row_index": row_idx, "detector": det.qualname}})
                continue

            duration_ms = round((perf_counter() - started) * 1000, 5)
            rounded_patch = {k: round(v, 6) for k, v in (patch or {}).items()}

            detector_payload = {
                "name": det.qualname,
                "scores": rounded_patch,
                "duration_ms": duration_ms,
            }

            detectors_run.append(detector_payload)

            if logger and logger.isEnabledFor(logging.DEBUG):
                scores_str = ", ".join(f"{k}={v:.3f}" for k, v in rounded_patch.items())
                detector_msg = (
                    f"Row {row_idx} detector {det.qualname} on {sheet_name}"
                    + (f" (scores {scores_str})" if scores_str else "")
                )
                logger.event(
                    "row_detector.result",
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
        if logger:
            row_score = scores.get(row_idx, {})
            if row_score:
                classification_type, classification_score = max(row_score.items(), key=lambda kv: kv[1])
            else:
                classification_type, classification_score = "unknown", 0.0

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
        else:
            # still track classification even when not logging
            row_score = scores.get(row_idx, {})
            if row_score:
                classification_type, _ = max(row_score.items(), key=lambda kv: kv[1])
            else:
                classification_type = "unknown"

        classifications.append(classification_type)

    return scores, classifications


def detect_table_bounds(
    *,
    sheet_name: str,
    rows: List[List[Any]],
    registry: Registry,
    state: dict,
    run_metadata: dict,
    logger: RunLogger,
) -> Tuple[int, int, int]:
    """Locate header row and data bounds using row classification sequence.

    Rules:
    - Use existing scoring/classification per row.
    - The first encountered header marks the header row; if a data row arrives
      before any header, assume the row immediately above is the header.
    - Data extends from the header row + 1 until the next header row (exclusive),
      or the end of the sheet if no subsequent header is found.
    """

    scores, classifications = _classify_rows(
        sheet_name=sheet_name,
        rows=rows,
        registry=registry,
        state=state,
        run_metadata=run_metadata,
        logger=logger,
    )

    header_idx = None
    header_inferred_from_data = False
    data_end_idx = len(rows)

    for idx, kind in enumerate(classifications):
        if header_idx is None:
            if kind == RowKind.HEADER.value:
                header_idx = idx
                header_inferred_from_data = False
            elif kind == RowKind.DATA.value and idx > 0:
                header_idx = idx - 1
                header_inferred_from_data = True
        else:
            if kind == RowKind.HEADER.value and idx > header_idx:
                if header_inferred_from_data:
                    # Upgrade to a concrete header and restart data tracking.
                    header_idx = idx
                    header_inferred_from_data = False
                    continue
                data_end_idx = idx
                break

    # Fallback: use best header score (original heuristic) if we still don't have a header.
    if header_idx is None:
        best_index = 0
        best_score = float("-inf")
        for idx in range(len(rows)):
            header_score = scores.get(idx, {}).get(RowKind.HEADER.value, 0.0)
            if header_score > best_score:
                best_score = header_score
                best_index = idx
        header_idx = best_index

        # If still no positive signal, choose first non-empty row.
        if best_score <= 0.0:
            for idx, row in enumerate(rows):
                if any(cell not in (None, "") for cell in row):
                    header_idx = idx
                    break

    data_start_idx = min(header_idx + 1, len(rows))

    if logger:
        logger.event(
            "row_detector.summary",
            level=logging.DEBUG,
            data={
                "sheet_name": sheet_name,
                "header_row_index": header_idx,
                "header_score": scores.get(header_idx, {}).get(RowKind.HEADER.value, 0.0),
                "data_start_index": data_start_idx,
                "data_end_index": data_end_idx,
                "scores": {idx: patch for idx, patch in scores.items() if patch},
            },
        )

    return header_idx, data_start_idx, data_end_idx


def detect_header_row(
    *,
    sheet_name: str,
    rows: List[List[Any]],
    registry: Registry,
    state: dict,
    run_metadata: dict,
    logger: RunLogger,
) -> int:
    """Backward-compatible helper returning only the header index."""
    header_idx, _, _ = detect_table_bounds(
        sheet_name=sheet_name,
        rows=rows,
        registry=registry,
        state=state,
        run_metadata=run_metadata,
        logger=logger,
    )
    return header_idx


__all__ = ["detect_header_row", "detect_table_bounds"]
