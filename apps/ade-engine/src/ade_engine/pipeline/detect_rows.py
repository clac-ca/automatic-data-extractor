from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Dict, List

from ade_engine.registry.models import RowDetectorContext, RowKind
from ade_engine.registry.registry import Registry
from ade_engine.logging import RunLogger


def detect_header_row(
    *,
    sheet_name: str,
    rows: List[List[Any]],
    registry: Registry,
    state: dict,
    run_metadata: dict,
    logger: RunLogger,
) -> int:
    """Run row detectors and pick the most likely header row index."""

    scores: Dict[int, Dict[str, float]] = {}
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
            except Exception as exc:  # pragma: no cover - defensive
                if logger:
                    logger.exception("Row detector failed", extra={"data": {"row_index": row_idx, "detector": det.qualname}})
                continue

            duration_ms = round((perf_counter() - started) * 1000, 5)  # keep sub-ms precision without large floats

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
                message=f"Row {row_idx} \u2192 {classification_type} ({logged_classification_score:.3f}) on {sheet_name}",
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

    # Pick header row.
    best_index = 0
    best_score = float("-inf")
    for idx in range(len(rows)):
        header_score = scores.get(idx, {}).get(RowKind.HEADER.value, 0.0)
        if header_score > best_score:
            best_score = header_score
            best_index = idx
    if best_score == float("-inf"):
        best_score = 0.0

    # Fallback: first non-empty row if detectors gave no signal.
    if best_score == 0.0:
        for idx, row in enumerate(rows):
            if any(cell not in (None, "") for cell in row):
                best_index = idx
                break

    if logger:
        logger.event(
            "row_detector.summary",
            level=logging.DEBUG,
            data={
                "sheet_name": sheet_name,
                "header_row_index": best_index,
                "header_score": scores.get(best_index, {}).get(RowKind.HEADER.value, 0.0),
                "scores": {idx: patch for idx, patch in scores.items() if patch},
            },
        )
    return best_index


__all__ = ["detect_header_row"]
