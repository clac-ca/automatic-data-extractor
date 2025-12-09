"""Normalization stage applying transforms and validators."""

from __future__ import annotations

from typing import Any

from ade_engine.config.loader import ConfigRuntime
from ade_engine.runtime import PluginInvoker
from ade_engine.types.contexts import RunContext
from ade_engine.types.issues import Severity, ValidationIssue
from ade_engine.types.tables import MappedTable, NormalizedTable


def _coerce_severity(value: Any) -> Severity:
    try:
        return Severity(str(value))
    except Exception:
        return Severity.ERROR


class TableNormalizer:
    def normalize(
        self,
        mapped: MappedTable,
        runtime: ConfigRuntime,
        run_ctx: RunContext,  # noqa: ARG002 - available via invoker.base_kwargs()
        *,
        invoker: PluginInvoker,
        logger=None,  # noqa: ARG002 - included for config callables
    ) -> NormalizedTable:
        manifest = runtime.manifest
        order = manifest.column_names
        field_configs = {col.name: col for col in manifest.columns}
        column_modules = runtime.columns

        mapped_fields = {field.field: field for field in mapped.mapping.fields}
        normalized_rows: list[list[object]] = []
        issues: list[ValidationIssue] = []

        for row_offset, source_row in enumerate(mapped.extracted.rows):
            source_row_index = mapped.region.min_row + 1 + row_offset  # 1-based row index on the source sheet

            canonical: dict[str, object | None] = {}
            for field_name in order:
                mapping = mapped_fields.get(field_name)
                source_col = mapping.source_col if mapping else None
                canonical[field_name] = (
                    source_row[source_col] if source_col is not None and source_col < len(source_row) else None
                )

            for field_name in order:
                transformer = column_modules[field_name].transformer
                if not transformer:
                    continue
                updates = invoker.call(
                    transformer,
                    row_index=source_row_index,
                    field_name=field_name,
                    value=canonical.get(field_name),
                    row=canonical,
                    field_config=field_configs.get(field_name),
                )
                if updates:
                    canonical.update(updates)

            for field_name in order:
                validator = column_modules[field_name].validator
                if not validator:
                    continue

                results = invoker.call(
                    validator,
                    row_index=source_row_index,
                    field_name=field_name,
                    value=canonical.get(field_name),
                    row=canonical,
                    field_config=field_configs.get(field_name),
                )

                for raw_issue in results or []:
                    if isinstance(raw_issue, ValidationIssue):
                        issues.append(raw_issue)
                        continue
                    if not isinstance(raw_issue, dict):
                        issues.append(
                            ValidationIssue(
                                row_index=row_offset,
                                field=field_name,
                                code="invalid_issue",
                                severity=Severity.ERROR,
                                message=str(raw_issue),
                                details=None,
                            )
                        )
                        continue

                    issues.append(
                        ValidationIssue(
                            row_index=row_offset,
                            field=field_name,
                            code=str(raw_issue.get("code") or ""),
                            severity=_coerce_severity(raw_issue.get("severity")),
                            message=raw_issue.get("message"),
                            details=raw_issue.get("details"),
                        )
                    )

            canonical_values = [canonical.get(field_name) for field_name in order]
            passthrough_values = [
                source_row[p.source_col] if p.source_col < len(source_row) else None for p in mapped.mapping.passthrough
            ]

            normalized_rows.append(canonical_values + passthrough_values)

        return NormalizedTable(
            origin=mapped.origin,
            region=mapped.region,
            header=mapped.mapping.output_header,
            rows=normalized_rows,
            issues=issues,
        )


__all__ = ["TableNormalizer"]
