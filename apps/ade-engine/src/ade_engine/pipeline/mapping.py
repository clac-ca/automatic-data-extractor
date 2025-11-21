"""Column mapping utilities."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any, Mapping, Sequence

from ade_engine.core.manifest import ColumnMeta
from ade_engine.core.models import JobContext
from ade_engine.core.pipeline_types import (
    ColumnMapping,
    ColumnModule,
    ExtraColumn,
    ScoreContribution,
)


def map_columns(
    job: JobContext,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    order: Sequence[str],
    meta: Mapping[str, Mapping[str, Any]],
    definitions: Mapping[str, ColumnMeta],
    modules: Mapping[str, ColumnModule],
    *,
    threshold: float,
    sample_size: int,
    append_unmapped: bool,
    prefix: str,
    table_info: Mapping[str, Any],
    state: Mapping[str, Any],
    logger: logging.Logger,
) -> tuple[list[ColumnMapping], list[ExtraColumn]]:
    """Score each input column and assign the best manifest field mapping."""

    mapping: list[ColumnMapping] = []
    extras: list[ExtraColumn] = []
    used_fields: set[str] = set()
    order_index = {field: idx for idx, field in enumerate(order)}

    normalized_headers = [normalize_header(value) for value in headers]
    column_values = [
        [row[idx] if idx < len(row) else None for row in rows]
        for idx in range(len(headers))
    ]

    table = dict(table_info)

    for idx, header in enumerate(headers):
        scores: dict[str, float] = defaultdict(float)
        contributions: list[ScoreContribution] = []
        normalized_header = normalized_headers[idx]
        values = column_values[idx]
        sample = column_sample(values, sample_size)
        column_tuple = tuple(values)

        for module in modules.values():
            for detector in module.detectors:
                try:
                    result = detector(
                        job=job,
                        state=state,
                        field_name=module.field,
                        field_meta=module.meta,
                        header=normalized_header,
                        column_values_sample=sample,
                        column_values=column_tuple,
                        table=table,
                        column_index=idx + 1,
                        logger=logger,
                    )
                except Exception as exc:  # pragma: no cover - detector failure
                    raise RuntimeError(
                        f"Detector '{detector.__module__}.{detector.__name__}' failed: {exc}"
                    ) from exc
                score_map = (result or {}).get("scores", {})
                for field, delta in score_map.items():
                    if field not in order_index:
                        continue
                    try:
                        delta_value = float(delta)
                    except (TypeError, ValueError):
                        continue
                    scores[field] = scores.get(field, 0.0) + delta_value
                    contributions.append(
                        ScoreContribution(
                            field=field,
                            detector=f"{detector.__module__}.{detector.__name__}",
                            delta=delta_value,
                        )
                    )

        chosen_field = None
        chosen_score = float("-inf")
        for field in order:
            if field in used_fields:
                continue
            score = scores.get(field)
            if score is None:
                continue
            if score < threshold:
                continue
            if score > chosen_score:
                chosen_field = field
                chosen_score = score
            elif score == chosen_score and chosen_field is not None:
                if order_index[field] < order_index[chosen_field]:
                    chosen_field = field
                    chosen_score = score

        if chosen_field is None and definitions:
            fallback = match_header(order, definitions, normalized_header, used_fields)
            if fallback is not None:
                chosen_field = fallback
                chosen_score = threshold

        if chosen_field:
            used_fields.add(chosen_field)
            selected = tuple(
                contrib for contrib in contributions if contrib.field == chosen_field
            )
            mapping.append(
                ColumnMapping(
                    field=chosen_field,
                    header=headers[idx],
                    index=idx,
                    score=chosen_score,
                    contributions=selected,
                )
            )
        elif append_unmapped:
            extras.append(
                ExtraColumn(
                    header=headers[idx],
                    index=idx,
                    output_header=build_unmapped_header(prefix, headers[idx], idx),
                )
            )

    return mapping, extras


def column_sample(values: Sequence[Any], size: int) -> list[Any]:
    """Return a spaced sample of ``values`` capped at ``size`` entries."""

    if size <= 0 or not values:
        return []
    if len(values) <= size:
        return list(values)
    count = max(1, size)
    step = len(values) / count
    sample: list[Any] = []
    index = 0.0
    while len(sample) < count:
        idx = int(index)
        if idx >= len(values):
            idx = len(values) - 1
        sample.append(values[idx])
        index += step
    if sample and sample[-1] != values[-1]:
        sample[-1] = values[-1]
    return sample


def build_unmapped_header(prefix: str, header: str, index: int) -> str:
    """Generate a sanitized header for unmapped columns."""

    cleaned = (
        re.sub(r"[^A-Za-z0-9]+", "_", header).strip("_").lower()
        or f"column_{index + 1}"
    )
    return f"{prefix}{cleaned}"[:31]


def normalize_header(value: str | None) -> str:
    """Normalize headers for comparison."""

    return (value or "").strip().lower()


def match_header(
    order: Sequence[str],
    meta: Mapping[str, ColumnMeta],
    normalized_header: str,
    used_fields: set[str],
) -> str | None:
    """Find a manifest field whose label/synonyms match the header."""

    candidate = normalized_header.strip()
    if not candidate:
        return None
    for field in order:
        if field in used_fields:
            continue
        info = meta.get(field)
        if info is None or not info.enabled:
            continue
        label = normalize_header(info.label or field)
        synonyms = [normalize_header(value) for value in info.synonyms]
        if candidate in {label, *synonyms}:
            return field
    return None


__all__ = [
    "build_unmapped_header",
    "column_sample",
    "map_columns",
    "match_header",
    "normalize_header",
]
