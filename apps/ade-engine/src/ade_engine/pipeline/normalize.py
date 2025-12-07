"""Normalization stage applying transforms and validators."""

from __future__ import annotations

from ade_engine.config.loader import ConfigRuntime
from ade_engine.types.contexts import RunContext
from ade_engine.types.issues import Severity, ValidationIssue
from ade_engine.types.tables import MappedTable, NormalizedTable


class TableNormalizer:
    def normalize(
        self,
        mapped: MappedTable,
        runtime: ConfigRuntime,
        run_ctx: RunContext,
        *,
        logger=None,
    ) -> NormalizedTable:
        manifest = runtime.manifest
        order = manifest.columns.order
        field_configs = manifest.columns.fields
        column_modules = runtime.columns
        state = run_ctx.state

        mapped_fields = {field.field: field for field in mapped.mapping.fields}
        normalized_rows: list[list[object]] = []
        issues: list[ValidationIssue] = []

        for offset, data_row in enumerate(mapped.extracted.rows):
            row_index = mapped.region.min_row + 1 + offset
            canonical_row: dict[str, object | None] = {}

            for field_name in order:
                mapped_field = mapped_fields.get(field_name)
                source_col = mapped_field.source_col if mapped_field else None
                value = data_row[source_col] if source_col is not None and source_col < len(data_row) else None
                canonical_row[field_name] = value

            for field_name in order:
                transform = column_modules[field_name].transformer
                if not transform:
                    continue
                updates = transform(
                    run=run_ctx,
                    state=state,
                    row_index=row_index,
                    field_name=field_name,
                    value=canonical_row.get(field_name),
                    row=canonical_row,
                    field_config=field_configs.get(field_name),
                    manifest=manifest,
                    logger=logger,
                    event_emitter=emitter,
                )
                if updates:
                    canonical_row.update(updates)

            for field_name in order:
                validator = column_modules[field_name].validator
                if not validator:
                    continue
                results = validator(
                    run=run_ctx,
                    state=state,
                    row_index=row_index,
                    field_name=field_name,
                    value=canonical_row.get(field_name),
                    row=canonical_row,
                    field_config=field_configs.get(field_name),
                    manifest=manifest,
                    logger=logger,
                    event_emitter=emitter,
                )
                for issue in results or []:
                    severity_value = issue.get("severity") if isinstance(issue, dict) else None
                    try:
                        severity = Severity(str(severity_value))
                    except Exception:
                        severity = Severity.ERROR
                    issues.append(
                        ValidationIssue(
                            row_index=offset,
                            field=field_name,
                            code=str(issue.get("code")) if isinstance(issue, dict) else "",
                            severity=severity,
                            message=issue.get("message") if isinstance(issue, dict) else None,
                            details=issue.get("details") if isinstance(issue, dict) else None,
                        )
                    )

            canonical_values = [canonical_row.get(field_name) for field_name in order]
            passthrough_values = []
            for p in mapped.mapping.passthrough:
                value = data_row[p.source_col] if p.source_col < len(data_row) else None
                passthrough_values.append(value)

            normalized_rows.append(canonical_values + passthrough_values)

        return NormalizedTable(
            origin=mapped.origin,
            region=mapped.region,
            header=mapped.mapping.output_header,
            rows=normalized_rows,
            issues=issues,
        )


__all__ = ["TableNormalizer"]
