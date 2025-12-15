from __future__ import annotations

import logging
from typing import Any

from ade_engine.logging import RunLogger
from ade_engine.pipeline.models import MappedColumn
from ade_engine.pipeline.patches import IssuesPatch, merge_issues_patch, normalize_validator_return
from ade_engine.pipeline.table_view import TableView
from ade_engine.registry.invoke import call_extension
from ade_engine.registry.models import ValidateContext
from ade_engine.registry.registry import Registry


def flatten_issues_patch(
    *,
    issues_patch: IssuesPatch,
    columns: dict[str, list[Any]],
    mapping: dict[str, int | None],
) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for field, vec in issues_patch.items():
        col = columns.get(field)
        column_index = mapping.get(field)
        for row_index, cell in enumerate(vec):
            if cell is None:
                continue
            issues: list[dict[str, Any]]
            if isinstance(cell, list):
                issues = cell
            else:
                issues = [cell]
            for issue in issues:
                flattened.append(
                    {
                        "field": field,
                        "row_index": row_index,
                        "message": issue.get("message"),
                        "severity": issue.get("severity"),
                        "code": issue.get("code"),
                        "meta": issue.get("meta"),
                        "value": (col[row_index] if col is not None and row_index < len(col) else None),
                        "column_index": column_index,
                    }
                )
    return flattened


def apply_validators(
    *,
    mapped_columns: list[MappedColumn],
    columns: dict[str, list[Any]],
    mapping: dict[str, int | None],
    registry: Registry,
    state: dict,
    metadata: dict,
    input_file_name: str | None,
    logger: RunLogger,
    row_count: int,
    initial_issues: IssuesPatch | None = None,
) -> IssuesPatch:
    """Apply validators using the v2 column-vector contract.
    """

    registry_fields = set(registry.fields.keys())
    validators_by_field = registry.column_validators_by_field
    debug = logger.isEnabledFor(logging.DEBUG)

    issues_patch: IssuesPatch = {}
    if initial_issues:
        merge_issues_patch(issues_patch, initial_issues)

    mapped_fields = [col.field_name for col in mapped_columns]
    mapped_set = set(mapped_fields)

    def run_field_validators(field_name: str) -> None:
        validators = validators_by_field.get(field_name, [])
        if not validators:
            return

        col = columns.get(field_name)
        if col is None:
            return

        for val in validators:
            ctx = ValidateContext(
                field_name=field_name,
                column=list(col),
                table=TableView(columns, mapping=mapping, row_count=row_count),
                mapping=mapping,
                state=state,
                metadata=metadata,
                input_file_name=input_file_name,
                logger=logger,
            )
            raw = call_extension(val.fn, ctx, label=f"Validator {val.qualname}")
            patch = normalize_validator_return(
                field_name=field_name,
                raw=raw,
                row_count=row_count,
                registry_fields=registry_fields,
                source=f"Validator {val.qualname}",
            )
            merge_issues_patch(issues_patch, patch.issues)

            if debug:
                logger.event(
                    "validation.result",
                    level=logging.DEBUG,
                    data={
                        "validator": val.qualname,
                        "field": field_name,
                        "issues_emitted_fields": sorted(patch.issues.keys()),
                    },
                )

    # Phase 1: mapped fields in source order.
    for field_name in mapped_fields:
        run_field_validators(field_name)

    # Phase 2: derived-only fields present in the table (deterministic registry order).
    for field_name in registry.fields.keys():
        if field_name in mapped_set:
            continue
        if field_name not in columns:
            continue
        run_field_validators(field_name)

    if debug:
        logger.event(
            "validation.summary",
            level=logging.DEBUG,
            data={
                "issues_total": sum(
                    1 for field in issues_patch for cell in issues_patch[field] if cell is not None
                )
            },
        )

    return issues_patch


__all__ = ["apply_validators", "flatten_issues_patch"]
