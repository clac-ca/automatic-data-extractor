"""Normalization pipeline stage."""

import logging
from typing import Any

from ade_engine.config.loader import ConfigRuntime
from ade_engine.infra.telemetry import EventEmitter
from ade_engine.core.types import MappedTable, NormalizedTable, RunContext, ValidationIssue


def normalize_table(
    *,
    ctx: RunContext,
    cfg: ConfigRuntime,
    mapped: MappedTable,
    logger: logging.Logger | None = None,
    event_emitter: EventEmitter,
) -> NormalizedTable:
    """Run transforms and validators to produce a normalized table.

    See ``05-normalization-and-validation.md`` for the expected behavior.
    """

    logger = logger or logging.getLogger(__name__)
    manifest = cfg.manifest
    mapped_lookup = {mc.field: mc for mc in mapped.column_map.mapped_columns}

    normalized_rows: list[list[Any]] = []
    validation_issues: list[ValidationIssue] = []

    for offset, data_row in enumerate(mapped.extracted.data_rows):
        row_index = mapped.extracted.first_data_row_index + offset
        row: dict[str, Any] = {}

        for field in manifest.columns.order:
            mapped_column = mapped_lookup.get(field)
            value = None
            if mapped_column and mapped_column.is_satisfied and mapped_column.source_column_index >= 0:
                source_idx = mapped_column.source_column_index
                value = data_row[source_idx] if source_idx < len(data_row) else None
            row[field] = value

        for field in manifest.columns.order:
            column_module = cfg.columns[field]
            if column_module.transformer:
                updates = column_module.transformer(
                    run=ctx,
                    state=ctx.state,
                    row_index=row_index,
                    field_name=field,
                    value=row.get(field),
                    row=row,
                    field_config=manifest.columns.fields.get(field),
                    manifest=manifest,
                    logger=logger,
                    event_emitter=event_emitter,
                )
                if updates:
                    row.update(updates)

        for field in manifest.columns.order:
            column_module = cfg.columns[field]
            if column_module.validator:
                results = column_module.validator(
                    run=ctx,
                    state=ctx.state,
                    row_index=row_index,
                    field_name=field,
                    value=row.get(field),
                    row=row,
                    field_config=manifest.columns.fields.get(field),
                    manifest=manifest,
                    logger=logger,
                    event_emitter=event_emitter,
                )
                for issue in results or []:
                    validation_issues.append(
                        ValidationIssue(
                            row_index=row_index,
                            field=field,
                            code=str(issue.get("code")),
                            severity=str(issue.get("severity")),
                            message=issue.get("message"),
                            details=issue.get("details"),
                        )
                    )

        canonical_values = [row.get(field) for field in manifest.columns.order]
        extra_values = []
        for unmapped in mapped.column_map.unmapped_columns:
            idx = unmapped.source_column_index
            extra_values.append(data_row[idx] if idx < len(data_row) else None)

        normalized_rows.append(canonical_values + extra_values)

    return NormalizedTable(
        mapped=mapped,
        rows=normalized_rows,
        validation_issues=validation_issues,
        output_sheet_name=manifest.writer.output_sheet,
    )


__all__ = ["normalize_table"]
