from __future__ import annotations

import logging
from typing import Any, Dict, List

from pydantic import ValidationError

from ade_engine.exceptions import PipelineError
from ade_engine.registry.invoke import call_extension
from ade_engine.models import ColumnValidatorResult
from ade_engine.pipeline.models import MappedColumn
from ade_engine.registry.models import ValidateContext
from ade_engine.registry.registry import Registry
from ade_engine.logging import RunLogger


def _validate_validation_output(
    *,
    field_name: str,
    validator_name: str,
    raw: Any,
    expected_len: int,
) -> List[ColumnValidatorResult]:
    """Validate validator output matches the strict issue contract."""

    if raw is None:
        raise PipelineError(
            f"Validator {validator_name} for field '{field_name}' must return a list of issues (got None)"
        )
    if not isinstance(raw, list):
        raise PipelineError(
            f"Validator {validator_name} for field '{field_name}' must return a list of issues"
        )

    validated: List[ColumnValidatorResult] = []
    for idx, item in enumerate(raw):
        try:
            entry = ColumnValidatorResult.model_validate(item)
        except ValidationError as exc:
            raise PipelineError(
                f"Validator {validator_name} for field '{field_name}' returned an invalid issue at position {idx}: {exc}"
            ) from exc
        if entry.row_index >= expected_len:
            raise PipelineError(
                f"Validator {validator_name} for field '{field_name}' produced out-of-range row_index {entry.row_index}"
            )
        validated.append(entry)

    return validated


def apply_validators(
    *,
    mapped_columns: List[MappedColumn],
    transformed_rows: List[Dict[str, Any]],
    registry: Registry,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger: RunLogger,
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    mapping_lookup = {col.field_name: col.source_index for col in mapped_columns}
    validators_by_field = registry.column_validators_by_field

    for col in mapped_columns:
        values = [row.get(col.field_name) for row in transformed_rows]
        expected_len = len(values)
        validators = validators_by_field.get(col.field_name, [])
        for val in validators:
            ctx = ValidateContext(
                field_name=col.field_name,
                values=values,
                mapping=mapping_lookup,
                state=state,
                metadata=metadata,
                column_index=col.source_index,
                input_file_name=input_file_name,
                logger=logger,
            )
            try:
                raw = call_extension(val.fn, ctx, label=f"Validator {val.qualname}")
                validated = _validate_validation_output(
                    field_name=col.field_name,
                    validator_name=val.qualname,
                    raw=raw,
                    expected_len=expected_len,
                )
            except Exception as exc:  # pragma: no cover
                raise PipelineError(
                    f"Validator {val.qualname} failed for field '{col.field_name}'"
                ) from exc
            logger.event(
                "validation.result",
                level=logging.DEBUG,
                data={
                    "validator": val.qualname,
                    "field": col.field_name,
                    "column_index": col.source_index,
                    "issues_found": len(validated),
                    "results_sample": [issue.model_dump() for issue in validated[:5]],
                },
            )
            for res in validated:
                issue = {
                    "field": col.field_name,
                    "row_index": res.row_index,
                    "column_index": col.source_index,
                    "message": res.message,
                    "value": values[res.row_index],
                }
                issues.append(issue)
    return issues


__all__ = ["apply_validators"]
