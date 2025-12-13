from __future__ import annotations

import logging
from typing import Any, Dict, List

from pydantic import ValidationError

from ade_engine.exceptions import PipelineError
from ade_engine.models import ColumnTransformResult
from ade_engine.registry.invoke import call_extension
from ade_engine.registry.models import TransformContext
from ade_engine.registry.registry import Registry
from ade_engine.pipeline.models import MappedColumn
from ade_engine.logging import RunLogger


def _wrap_base_values(field_name: str, values: List[Any]) -> List[ColumnTransformResult]:
    """Wrap raw column values into the standard row output shape."""

    return [
        ColumnTransformResult(row_index=idx, value={field_name: value})
        for idx, value in enumerate(values)
    ]


def _validate_transform_output(
    *,
    field_name: str,
    transform_name: str,
    raw: Any,
    expected_len: int,
) -> List[ColumnTransformResult]:
    """Validate transform output matches the strict row-output contract."""

    if raw is None:
        raise PipelineError(
            f"Transform {transform_name} for field '{field_name}' returned None; expected a list of row outputs"
        )
    if not isinstance(raw, list):
        raise PipelineError(
            f"Transform {transform_name} for field '{field_name}' must return a list of row outputs"
        )
    if len(raw) != expected_len:
        raise PipelineError(
            f"Transform {transform_name} for field '{field_name}' must return {expected_len} row outputs (got {len(raw)})"
        )

    validated: List[ColumnTransformResult] = []
    seen_indices: set[int] = set()
    for idx, item in enumerate(raw):
        try:
            entry = ColumnTransformResult.model_validate(item)
        except ValidationError as exc:
            raise PipelineError(
                f"Transform {transform_name} for field '{field_name}' returned an invalid row payload at position {idx}: {exc}"
            ) from exc

        if entry.row_index in seen_indices:
            raise PipelineError(
                f"Transform {transform_name} for field '{field_name}' returned duplicate row_index {entry.row_index}"
            )
        if entry.row_index >= expected_len:
            raise PipelineError(
                f"Transform {transform_name} for field '{field_name}' produced out-of-range row_index {entry.row_index}"
            )
        seen_indices.add(entry.row_index)
        validated.append(entry)

    missing_indices = set(range(expected_len)) - seen_indices
    if missing_indices:
        missing_str = ", ".join(str(idx) for idx in sorted(missing_indices))
        raise PipelineError(
            f"Transform {transform_name} for field '{field_name}' missing rows at indices {missing_str}"
        )

    validated.sort(key=lambda entry: entry.row_index)
    return validated


def apply_transforms(
    *,
    mapped_columns: List[MappedColumn],
    registry: Registry,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger: RunLogger,
) -> List[Dict[str, Any]]:
    if not mapped_columns:
        return []

    row_count = max(len(col.values) for col in mapped_columns)
    output_rows: List[Dict[str, Any]] = [dict() for _ in range(row_count)]

    mapping_lookup = {col.field_name: col.source_index for col in mapped_columns}
    transforms_by_field = registry.column_transforms_by_field

    for col in mapped_columns:
        expected_len = len(col.values)
        working = _wrap_base_values(col.field_name, list(col.values))
        current_values: List[Any] = list(col.values)

        transforms = transforms_by_field.get(col.field_name, [])
        for tf in transforms:
            before_sample = current_values[:3]
            ctx = TransformContext(
                field_name=col.field_name,
                values=current_values,
                mapping=mapping_lookup,
                state=state,
                metadata=metadata,
                input_file_name=input_file_name,
                logger=logger,
            )
            try:
                raw_out = call_extension(tf.fn, ctx, label=f"Transform {tf.qualname}")
                validated = _validate_transform_output(
                    field_name=col.field_name,
                    transform_name=tf.qualname,
                    raw=raw_out,
                    expected_len=expected_len,
                )
            except Exception as exc:  # pragma: no cover - defensive
                raise PipelineError(
                    f"Transform {tf.qualname} failed for field '{col.field_name}'"
                ) from exc
            logger.event(
                "transform.result",
                level=logging.DEBUG,
                data={
                    "transform": tf.qualname,
                    "field": col.field_name,
                    "input_len": expected_len,
                    "output_len": len(validated),
                    "sample_before": before_sample,
                    "sample_after": [entry.value for entry in validated[:3]],
                },
            )
            working = validated
            current_values = [entry.value for entry in working]

        # merge into output rows
        for row_data in working:
            row_index = row_data.row_index
            if row_index >= len(output_rows):
                output_rows.extend({} for _ in range(row_index - len(output_rows) + 1))
            value_payload = dict(row_data.value) if row_data.value is not None else {}
            if col.field_name not in value_payload:
                value_payload[col.field_name] = None
            for key, value in value_payload.items():
                if key in output_rows[row_index] and output_rows[row_index][key] != value:
                    logger.event(
                        "transform.overwrite",
                        level=logging.DEBUG,
                        data={"field": key, "row_index": row_index},
                    )
                output_rows[row_index][key] = value

    return output_rows


__all__ = ["apply_transforms"]
