from __future__ import annotations

import logging
from typing import Any, Dict, List

from ade_engine.pipeline.models import MappedColumn
from ade_engine.registry.models import ValidateContext
from ade_engine.registry.registry import Registry
from ade_engine.logging import RunLogger


def _normalize_validation_output(raw: Any) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, bool):
        return [] if raw else [{"passed": False}]
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        out: List[Dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict):
                out.append(item)
        return out
    return []


def apply_validators(
    *,
    mapped_columns: List[MappedColumn],
    transformed_rows: List[Dict[str, Any]],
    registry: Registry,
    state: dict,
    run_metadata: dict,
    logger: RunLogger,
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    mapping_lookup = {col.field_name: col.source_index for col in mapped_columns}

    for col in mapped_columns:
        values = [row.get(col.field_name) for row in transformed_rows]
        validators = [v for v in registry.column_validators if v.field == col.field_name]
        for val in validators:
            ctx = ValidateContext(
                field_name=col.field_name,
                values=values,
                mapping=mapping_lookup,
                state=state,
                run_metadata=run_metadata,
                column_index=col.source_index,
                logger=logger,
            )
            try:
                raw = val.fn(ctx)
                normalized = _normalize_validation_output(raw)
            except Exception as exc:  # pragma: no cover
                if logger:
                    logger.exception(
                        "Validator failed",
                        extra={"data": {"field": col.field_name, "validator": val.qualname}},
                    )
                continue
            if logger:
                logger.event(
                    "validator.result",
                    level=logging.DEBUG,
                    data={
                        "validator": val.qualname,
                        "field": col.field_name,
                        "column_index": col.source_index,
                        "issues_found": len([res for res in normalized if not res.get("passed", True)]),
                        "results_sample": normalized[:5],
                    },
                )
            for res in normalized:
                passed = res.get("passed", True)
                if not passed:
                    issue = {
                        "field": col.field_name,
                        "row_index": res.get("row_index"),
                        "column_index": res.get("column_index", col.source_index),
                        "message": res.get("message"),
                        "value": res.get("value"),
                    }
                    issues.append(issue)
    return issues


__all__ = ["apply_validators"]
