from __future__ import annotations

import logging
from typing import Any, Dict, List

from ade_engine.registry.models import TransformContext
from ade_engine.registry.registry import Registry
from ade_engine.pipeline.models import MappedColumn
from ade_engine.logging import RunLogger


def _normalize_transform_output(field_name: str, raw: Any, expected_len: int) -> List[Dict[str, Any]]:
    if raw is None:
        return [{field_name: None} for _ in range(expected_len)]
    if not isinstance(raw, list):
        raise ValueError("Transform must return a list aligned to input rows")
    if len(raw) != expected_len:
        raise ValueError("Transform output length must match input rows")

    normalized: List[Dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            if field_name not in item:
                # ensure current field is present even if None
                item = {field_name: None, **item}
            normalized.append(dict(item))
        else:
            normalized.append({field_name: item})
    return normalized


def apply_transforms(
    *,
    mapped_columns: List[MappedColumn],
    registry: Registry,
    state: dict,
    run_metadata: dict,
    logger: RunLogger,
) -> List[Dict[str, Any]]:
    if not mapped_columns:
        return []

    row_count = max(len(col.values) for col in mapped_columns)
    output_rows: List[Dict[str, Any]] = [dict() for _ in range(row_count)]

    mapping_lookup = {col.field_name: col.source_index for col in mapped_columns}

    for col in mapped_columns:
        # base values from source column
        working = [{col.field_name: v} for v in col.values]

        transforms = [tf for tf in registry.column_transforms if tf.field == col.field_name]
        for tf in transforms:
            before_sample = working[:3]
            ctx = TransformContext(
                field_name=col.field_name,
                values=[row.get(col.field_name) for row in working],
                mapping=mapping_lookup,
                state=state,
                run_metadata=run_metadata,
                logger=logger,
            )
            try:
                raw_out = tf.fn(ctx)
                normalized = _normalize_transform_output(col.field_name, raw_out, len(working))
            except Exception as exc:  # pragma: no cover - defensive
                if logger:
                    logger.exception("Transform failed", extra={"data": {"field": col.field_name, "transform": tf.qualname}})
                normalized = working
            if logger:
                logger.event(
                    "transform.applied",
                    level=logging.DEBUG,
                    data={
                        "transform": tf.qualname,
                        "field": col.field_name,
                        "input_len": len(working),
                        "output_len": len(normalized),
                        "sample_before": before_sample,
                        "sample_after": normalized[:3],
                    },
                )
            working = normalized

        # merge into output rows
        for idx, row_data in enumerate(working):
            for key, value in row_data.items():
                if key in output_rows[idx] and output_rows[idx][key] != value and logger:
                    logger.event(
                        "transform.overwrite",
                        level=logging.DEBUG,
                        data={"field": key, "row_index": idx},
                    )
                output_rows[idx][key] = value

    return output_rows


__all__ = ["apply_transforms"]
