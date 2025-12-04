"""Aggregation of table-level facts into sheet/file/run summaries."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable
from uuid import UUID

from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.types import NormalizedTable, RunContext, RunError, RunStatus
from ade_engine.infra.telemetry import _coerce_uuid
from ade_engine.schemas import (
    ColumnCounts,
    ColumnSummaryDistinct,
    ColumnSummaryTable,
    Counts,
    FieldCounts,
    FieldSummaryAggregate,
    FieldSummaryTable,
    FileSummary,
    ManifestV1,
    RowCounts,
    RunSummary,
    SheetSummary,
    TableSummary,
    ValidationSummary,
)


@dataclass
class _FieldInfo:
    label: str | None
    required: bool


@dataclass
class _FieldAggState:
    field: str
    label: str | None
    required: bool
    mapped: bool = False
    max_score: float | None = None
    tables: set[str] = field(default_factory=set)
    sheets: set[str] = field(default_factory=set)
    files: set[str] = field(default_factory=set)


@dataclass
class _DistinctHeaderState:
    header: str
    header_normalized: str
    tables_seen: set[str] = field(default_factory=set)
    physical_columns_seen: int = 0
    physical_columns_non_empty: int = 0
    physical_columns_mapped: int = 0
    mapped_fields: Counter[str] = field(default_factory=Counter)
    mapped: bool = False


@dataclass
class _ValidationAggState:
    rows_evaluated: int = 0
    issues_total: int = 0
    issues_by_severity: Counter[str] = field(default_factory=Counter)
    issues_by_code: Counter[str] = field(default_factory=Counter)
    issues_by_field: Counter[str] = field(default_factory=Counter)
    max_severity: str | None = None


@dataclass
class _ScopeState:
    id: str
    parent_ids: dict[str, str]
    source: dict[str, Any]
    field_states: dict[str, _FieldAggState]
    distinct_headers: dict[str, _DistinctHeaderState] = field(default_factory=dict)
    validation: _ValidationAggState = field(default_factory=_ValidationAggState)
    rows_total: int = 0
    rows_empty: int = 0
    columns_physical_total: int = 0
    columns_physical_empty: int = 0
    table_ids: list[str] = field(default_factory=list)
    sheet_ids: list[str] = field(default_factory=list)
    file_ids: list[str] = field(default_factory=list)


def _is_empty_cell(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _normalize_header(header: str) -> str:
    return header.strip().lower()


def _severity_rank(value: str | None) -> int:
    if value is None:
        return 0
    normalized = value.lower()
    if normalized == "error":
        return 3
    if normalized == "warning":
        return 2
    if normalized == "info":
        return 1
    return 0


class SummaryAggregator:
    """Build table, sheet, file, and run summaries during pipeline execution."""

    def __init__(
        self,
        *,
        run: RunContext,
        manifest: ManifestV1 | ManifestContext | None,
        engine_version: str | None = None,
        config_version: str | None = None,
    ) -> None:
        self.run = run
        self.manifest = manifest.model if isinstance(manifest, ManifestContext) else manifest
        self.engine_version = engine_version
        self.config_version = config_version or (self.manifest.version if self.manifest else None)

        metadata = run.metadata or {}
        self.workspace_id = _coerce_uuid(metadata.get("workspace_id"))
        self.configuration_id = _coerce_uuid(metadata.get("configuration_id"))
        self.run_id = _coerce_uuid(metadata.get("run_id")) or run.run_id
        self.build_id = _coerce_uuid(metadata.get("build_id"))
        self.env_reason = metadata.get("env_reason")
        env_reused = metadata.get("env_reused")
        if isinstance(env_reused, str):
            self.env_reused = env_reused.lower() in {"1", "true", "yes", "y"}
        else:
            self.env_reused = env_reused

        self._field_catalog: dict[str, _FieldInfo] = {}
        self._field_order: list[str] = []
        self._tables: list[TableSummary] = []
        self._table_counter = 0
        self._file_counter = 0
        self._sheet_counter = 0

        self._file_states: dict[str, _ScopeState] = {}
        self._sheet_states: dict[tuple[str, str | None], _ScopeState] = {}
        self._run_state = _ScopeState(
            id="run",
            parent_ids={"run_id": str(self.run_id)},
            source={
                "run_id": str(self.run_id),
                "workspace_id": str(self.workspace_id) if self.workspace_id else None,
                "configuration_id": str(self.configuration_id) if self.configuration_id else None,
                "build_id": str(self.build_id) if self.build_id else None,
                "engine_version": engine_version,
                "config_version": self.config_version,
                "started_at": run.started_at,
                "env_reason": self.env_reason,
                "env_reused": self.env_reused,
            },
            field_states={},
        )

        if self.manifest:
            for field_name in self.manifest.columns.order:
                field_model = self.manifest.columns.fields[field_name]
                self._register_field(field_name, field_model.label, bool(field_model.required))
        # Make sure the run scope has all catalog fields
        for name in list(self._field_catalog.keys()):
            self._run_state.field_states.setdefault(
                name,
                _FieldAggState(
                    field=name,
                    label=self._field_catalog[name].label,
                    required=self._field_catalog[name].required,
                ),
            )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def add_table(self, table: NormalizedTable) -> TableSummary:
        """Build a TableSummary for ``table`` and update aggregate states."""

        file_path = str(table.mapped.extracted.source_file)
        sheet_name = table.mapped.extracted.source_sheet

        file_state = self._file_states.get(file_path)
        if file_state is None:
            file_state = self._create_file_state(file_path)
            self._file_states[file_path] = file_state
        sheet_key = (file_path, sheet_name)
        sheet_state = self._sheet_states.get(sheet_key)
        if sheet_state is None:
            sheet_state = self._create_sheet_state(sheet_key, file_state.id, file_path, sheet_name)
            self._sheet_states[sheet_key] = sheet_state
            file_state.sheet_ids.append(sheet_state.id)
            if sheet_state.id not in self._run_state.sheet_ids:
                self._run_state.sheet_ids.append(sheet_state.id)

        table_id = f"tbl_{self._table_counter}"
        self._table_counter += 1

        table_summary = self._build_table_summary(
            table=table,
            table_id=table_id,
            file_id=file_state.id,
            sheet_id=sheet_state.id,
        )
        self._tables.append(table_summary)

        self._update_scope_from_table(sheet_state, table_summary, file_id=file_state.id, sheet_id=sheet_state.id)
        self._update_scope_from_table(file_state, table_summary, file_id=file_state.id, sheet_id=sheet_state.id)
        self._update_scope_from_table(self._run_state, table_summary, file_id=file_state.id, sheet_id=sheet_state.id)

        sheet_state.table_ids.append(table_id)
        file_state.table_ids.append(table_id)
        self._run_state.table_ids.append(table_id)
        if file_state.id not in self._run_state.file_ids:
            self._run_state.file_ids.append(file_state.id)

        return table_summary

    def finalize(
        self,
        *,
        status: RunStatus,
        failure: RunError | None = None,
        completed_at: datetime | None = None,
        output_paths: Iterable[str] | None = None,
        processed_files: Iterable[str] | None = None,
    ) -> tuple[list[SheetSummary], list[FileSummary], RunSummary]:
        """Return aggregate sheet/file/run summaries."""

        self._run_state.source["completed_at"] = completed_at
        self._run_state.source["status"] = status.value if hasattr(status, "value") else str(status)

        failure_payload = {
            "code": getattr(getattr(failure, "code", None), "value", None) if failure else None,
            "stage": getattr(getattr(failure, "stage", None), "value", None) if failure else None,
            "message": getattr(failure, "message", None) if failure else None,
        }
        self._run_state.source["failure"] = {k: v for k, v in failure_payload.items() if v is not None}

        sheet_summaries = [self._build_sheet_summary(state) for state in self._sheet_states.values()]
        file_summaries = [self._build_file_summary(state) for state in self._file_states.values()]
        run_summary = self._build_run_summary(
            output_paths=output_paths,
            processed_files=processed_files,
        )
        return sheet_summaries, file_summaries, run_summary

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _register_field(self, name: str, label: str | None, required: bool) -> None:
        if name in self._field_catalog:
            return
        self._field_catalog[name] = _FieldInfo(label=label, required=required)
        self._field_order.append(name)
        for state in self._file_states.values():
            state.field_states[name] = _FieldAggState(field=name, label=label, required=required)
        for state in self._sheet_states.values():
            state.field_states[name] = _FieldAggState(field=name, label=label, required=required)
        self._run_state.field_states[name] = _FieldAggState(field=name, label=label, required=required)

    def _create_file_state(self, file_path: str) -> _ScopeState:
        file_id = f"file_{self._file_counter}"
        self._file_counter += 1
        field_states = {
            name: _FieldAggState(field=name, label=info.label, required=info.required)
            for name, info in self._field_catalog.items()
        }
        return _ScopeState(
            id=file_id,
            parent_ids={"run_id": str(self.run_id)},
            source={"file_path": file_path},
            field_states=field_states,
        )

    def _create_sheet_state(
        self,
        sheet_key: tuple[str, str | None],
        file_id: str,
        file_path: str,
        sheet_name: str | None,
    ) -> _ScopeState:
        sheet_id = f"sheet_{self._sheet_counter}"
        self._sheet_counter += 1
        field_states = {
            name: _FieldAggState(field=name, label=info.label, required=info.required)
            for name, info in self._field_catalog.items()
        }
        return _ScopeState(
            id=sheet_id,
            parent_ids={"run_id": str(self.run_id), "file_id": file_id},
            source={"file_path": file_path, "sheet_name": sheet_name},
            field_states=field_states,
        )

    def _build_table_summary(
        self,
        *,
        table: NormalizedTable,
        table_id: str,
        file_id: str,
        sheet_id: str,
    ) -> TableSummary:
        extracted = table.mapped.extracted
        mapped_columns = list(table.mapped.column_map.mapped_columns)
        unmapped_columns = list(table.mapped.column_map.unmapped_columns)
        all_columns = mapped_columns + unmapped_columns

        # Ensure catalog covers any new fields observed on this table.
        for column in mapped_columns:
            if column.field not in self._field_catalog:
                self._register_field(column.field, label=None, required=False)

        column_indices = [column.source_column_index for column in all_columns]
        non_empty_counts: dict[int, int] = {idx: 0 for idx in column_indices}
        empty_rows = 0
        for row in table.rows:
            row_empty = True
            for idx in column_indices:
                value = row[idx] if idx < len(row) else None
                if not _is_empty_cell(value):
                    non_empty_counts[idx] = non_empty_counts.get(idx, 0) + 1
                    row_empty = False
            if row_empty:
                empty_rows += 1

        column_summaries: list[ColumnSummaryTable] = []
        header_mapped_flags: dict[str, bool] = {}

        field_best: dict[str, tuple[float, ColumnSummaryTable]] = {}
        for column in mapped_columns:
            non_empty_row_count = non_empty_counts.get(column.source_column_index, 0)
            col_summary = ColumnSummaryTable(
                source_column_index=column.source_column_index,
                header=column.header,
                empty=non_empty_row_count == 0,
                non_empty_row_count=non_empty_row_count,
                mapped=True,
                mapped_field=column.field,
                mapped_field_label=self._field_catalog.get(column.field, _FieldInfo(None, False)).label,
                score=float(column.score),
                output_header=None,
            )
            column_summaries.append(col_summary)
            header_mapped_flags[col_summary.header] = True
            if column.is_satisfied:
                current = field_best.get(column.field)
                if current is None or float(column.score) > current[0]:
                    field_best[column.field] = (float(column.score), col_summary)

        for column in unmapped_columns:
            non_empty_row_count = non_empty_counts.get(column.source_column_index, 0)
            col_summary = ColumnSummaryTable(
                source_column_index=column.source_column_index,
                header=column.header,
                empty=non_empty_row_count == 0,
                non_empty_row_count=non_empty_row_count,
                mapped=False,
                mapped_field=None,
                mapped_field_label=None,
                score=None,
                output_header=column.output_header,
            )
            column_summaries.append(col_summary)
            header_mapped_flags.setdefault(col_summary.header, False)

        column_summaries.sort(key=lambda col: col.source_column_index)

        field_summaries: list[FieldSummaryTable] = []
        mapped_fields = {name for name, _ in field_best.items()}
        required_fields = {name for name, info in self._field_catalog.items() if info.required}

        for field_name in self._field_order:
            info = self._field_catalog[field_name]
            best = field_best.get(field_name)
            field_summaries.append(
                FieldSummaryTable(
                    field=field_name,
                    label=info.label,
                    required=info.required,
                    mapped=field_name in mapped_fields,
                    score=best[0] if best else None,
                    source_column_index=best[1].source_column_index if best else None,
                    header=best[1].header if best else None,
                )
            )

        total_fields = len(self._field_catalog)
        required_count = len(required_fields)
        mapped_count = len(mapped_fields)
        required_mapped_count = len(required_fields & mapped_fields)
        rows_total = len(table.rows)

        counts = Counts(
            rows=RowCounts(total=rows_total, empty=empty_rows, non_empty=max(rows_total - empty_rows, 0)),
            columns=ColumnCounts(
                physical_total=len(column_summaries),
                physical_empty=len([col for col in column_summaries if col.empty]),
                physical_non_empty=len([col for col in column_summaries if not col.empty]),
                distinct_headers=len(header_mapped_flags),
                distinct_headers_mapped=len([flag for flag in header_mapped_flags.values() if flag]),
                distinct_headers_unmapped=len([flag for flag in header_mapped_flags.values() if not flag]),
            ),
            fields=FieldCounts(
                total=total_fields,
                required=required_count,
                mapped=mapped_count,
                unmapped=max(total_fields - mapped_count, 0),
                required_mapped=required_mapped_count,
                required_unmapped=max(required_count - required_mapped_count, 0),
            ),
        )

        validation_summary = self._build_validation_summary(
            issues=table.validation_issues,
            rows_evaluated=rows_total,
        )

        return TableSummary(
            id=table_id,
            parent_ids={"run_id": str(self.run_id), "file_id": file_id, "sheet_id": sheet_id},
            source={
                "file_path": str(extracted.source_file),
                "sheet_name": extracted.source_sheet,
                "table_index": extracted.table_index,
                "output_sheet": table.output_sheet_name,
            },
            counts=counts,
            fields=field_summaries,
            columns=column_summaries,
            validation=validation_summary,
            details={
                "header_row_index": extracted.header_row_index,
                "first_data_row_index": extracted.first_data_row_index,
                "last_data_row_index": extracted.last_data_row_index,
            },
        )

    def _build_validation_summary(
        self,
        *,
        issues: Iterable[Any],
        rows_evaluated: int,
    ) -> ValidationSummary:
        issues_total = 0
        issues_by_severity: Counter[str] = Counter()
        issues_by_code: Counter[str] = Counter()
        issues_by_field: Counter[str] = Counter()
        max_severity: str | None = None
        for issue in issues:
            issues_total += 1
            severity = getattr(issue, "severity", None) or None
            code = getattr(issue, "code", None) or None
            field_name = getattr(issue, "field", None) or None
            severity_str = str(severity).lower() if severity else None
            code_str = str(code) if code else None
            field_str = str(field_name) if field_name else None
            if severity_str:
                issues_by_severity[severity_str] += 1
                if _severity_rank(severity_str) > _severity_rank(max_severity):
                    max_severity = severity_str
            if code_str:
                issues_by_code[code_str] += 1
            if field_str:
                issues_by_field[field_str] += 1
        return ValidationSummary(
            rows_evaluated=rows_evaluated,
            issues_total=issues_total,
            issues_by_severity=dict(issues_by_severity),
            issues_by_code=dict(issues_by_code),
            issues_by_field=dict(issues_by_field),
            max_severity=max_severity,
        )

    def _update_scope_from_table(
        self,
        state: _ScopeState,
        table: TableSummary,
        *,
        file_id: str,
        sheet_id: str,
    ) -> None:
        state.rows_total += table.counts.rows.total
        state.rows_empty += table.counts.rows.empty
        state.columns_physical_total += table.counts.columns.physical_total
        state.columns_physical_empty += table.counts.columns.physical_empty

        self._merge_validation(state.validation, table.validation)
        self._merge_columns(state.distinct_headers, table.columns, table_id=table.id)
        self._merge_fields(
            state.field_states,
            table.fields,
            table_id=table.id,
            sheet_id=sheet_id,
            file_id=file_id,
        )

    @staticmethod
    def _merge_validation(target: _ValidationAggState, incoming: ValidationSummary) -> None:
        target.rows_evaluated += incoming.rows_evaluated
        target.issues_total += incoming.issues_total
        for sev, count in incoming.issues_by_severity.items():
            target.issues_by_severity[sev] += count
        for code, count in incoming.issues_by_code.items():
            target.issues_by_code[code] += count
        for field, count in incoming.issues_by_field.items():
            target.issues_by_field[field] += count
        if _severity_rank(incoming.max_severity) > _severity_rank(target.max_severity):
            target.max_severity = incoming.max_severity

    def _merge_columns(
        self,
        target: dict[str, _DistinctHeaderState],
        columns: list[ColumnSummaryTable],
        *,
        table_id: str,
    ) -> None:
        seen_in_table: set[str] = set()
        for column in columns:
            normalized = _normalize_header(column.header)
            state = target.get(normalized)
            if state is None:
                state = _DistinctHeaderState(header=column.header, header_normalized=normalized)
                target[normalized] = state
            if normalized not in seen_in_table:
                state.tables_seen.add(table_id)
                seen_in_table.add(normalized)
            state.physical_columns_seen += 1
            if not column.empty:
                state.physical_columns_non_empty += 1
            if column.mapped:
                state.physical_columns_mapped += 1
                state.mapped = True
                if column.mapped_field:
                    state.mapped_fields[column.mapped_field] += 1

    def _merge_fields(
        self,
        target: dict[str, _FieldAggState],
        fields: list[FieldSummaryTable],
        *,
        table_id: str,
        sheet_id: str,
        file_id: str,
    ) -> None:
        for field in fields:
            state = target.get(field.field)
            if state is None:
                state = _FieldAggState(field=field.field, label=field.label, required=field.required)
                target[field.field] = state
            if field.mapped:
                state.mapped = True
                if field.score is not None:
                    current = state.max_score if state.max_score is not None else float("-inf")
                    state.max_score = max(current, float(field.score))
                state.tables.add(table_id)
                state.sheets.add(sheet_id)
                state.files.add(file_id)

    def _build_sheet_summary(self, state: _ScopeState) -> SheetSummary:
        self._ensure_field_states(state)
        columns = self._build_distinct_columns(state.distinct_headers)
        counts = self._build_counts(state, scope="sheet", distinct_columns=columns)
        fields = self._build_field_aggregates(state.field_states, scope="sheet")
        validation = self._build_validation_aggregate(state.validation)
        return SheetSummary(
            id=state.id,
            parent_ids=state.parent_ids,
            source=state.source,
            counts=counts,
            fields=fields,
            columns=columns,
            validation=validation,
            details={"table_ids": list(state.table_ids)},
        )

    def _build_file_summary(self, state: _ScopeState) -> FileSummary:
        self._ensure_field_states(state)
        columns = self._build_distinct_columns(state.distinct_headers)
        counts = self._build_counts(state, scope="file", distinct_columns=columns)
        fields = self._build_field_aggregates(state.field_states, scope="file")
        validation = self._build_validation_aggregate(state.validation)
        return FileSummary(
            id=state.id,
            parent_ids=state.parent_ids,
            source=state.source,
            counts=counts,
            fields=fields,
            columns=columns,
            validation=validation,
            details={"sheet_ids": list(state.sheet_ids), "table_ids": list(state.table_ids)},
        )

    def _build_run_summary(
        self,
        *,
        output_paths: Iterable[str] | None,
        processed_files: Iterable[str] | None,
    ) -> RunSummary:
        state = self._run_state
        self._ensure_field_states(state)
        columns = self._build_distinct_columns(state.distinct_headers)
        counts = self._build_counts(state, scope="run", distinct_columns=columns)
        fields = self._build_field_aggregates(state.field_states, scope="run")
        validation = self._build_validation_aggregate(state.validation)
        details: dict[str, Any] = {
            "file_ids": list(state.file_ids),
            "sheet_ids": list(state.sheet_ids),
            "table_ids": list(state.table_ids),
        }
        if output_paths is not None:
            details["output_paths"] = list(output_paths)
        if processed_files is not None:
            details["processed_files"] = list(processed_files)
        return RunSummary(
            id=state.id,
            parent_ids=state.parent_ids,
            source=state.source,
            counts=counts,
            fields=fields,
            columns=columns,
            validation=validation,
            details=details,
        )

    def _build_distinct_columns(
        self,
        headers: dict[str, _DistinctHeaderState],
    ) -> list[ColumnSummaryDistinct]:
        summaries: list[ColumnSummaryDistinct] = []
        for state in headers.values():
            mapped_fields_counts = dict(state.mapped_fields)
            mapped_fields = sorted(mapped_fields_counts.keys())
            occurrences = {
                "tables_seen": len(state.tables_seen),
                "physical_columns_seen": state.physical_columns_seen,
                "physical_columns_non_empty": state.physical_columns_non_empty,
                "physical_columns_mapped": state.physical_columns_mapped,
            }
            summaries.append(
                ColumnSummaryDistinct(
                    header=state.header,
                    header_normalized=state.header_normalized,
                    occurrences=occurrences,
                    mapped=state.mapped,
                    mapped_fields=mapped_fields,
                    mapped_fields_counts=mapped_fields_counts,
                )
            )
        return sorted(summaries, key=lambda col: col.header_normalized)

    def _build_counts(
        self,
        state: _ScopeState,
        *,
        scope: str,
        distinct_columns: list[ColumnSummaryDistinct],
    ) -> Counts:
        field_total = len(self._field_catalog)
        required_total = len([info for info in self._field_catalog.values() if info.required])
        mapped_fields = len([field for field in state.field_states.values() if field.mapped])
        required_mapped = len([field for field in state.field_states.values() if field.required and field.mapped])
        distinct_headers = len(distinct_columns)
        distinct_headers_mapped = len([col for col in distinct_columns if col.mapped])
        distinct_headers_unmapped = distinct_headers - distinct_headers_mapped

        counts = Counts(
            rows=RowCounts(
                total=state.rows_total,
                empty=state.rows_empty,
                non_empty=max(state.rows_total - state.rows_empty, 0),
            ),
            columns=ColumnCounts(
                physical_total=state.columns_physical_total,
                physical_empty=state.columns_physical_empty,
                physical_non_empty=max(state.columns_physical_total - state.columns_physical_empty, 0),
                distinct_headers=distinct_headers,
                distinct_headers_mapped=distinct_headers_mapped,
                distinct_headers_unmapped=distinct_headers_unmapped,
            ),
            fields=FieldCounts(
                total=field_total,
                required=required_total,
                mapped=mapped_fields,
                unmapped=max(field_total - mapped_fields, 0),
                required_mapped=required_mapped,
                required_unmapped=max(required_total - required_mapped, 0),
            ),
        )

        if scope == "sheet":
            counts.tables = {"total": len(state.table_ids)}
        if scope == "file":
            counts.tables = {"total": len(state.table_ids)}
            counts.sheets = {"total": len(state.sheet_ids)}
        if scope == "run":
            counts.tables = {"total": len(state.table_ids)}
            counts.sheets = {"total": len(state.sheet_ids)}
            counts.files = {"total": len(state.file_ids)}
        return counts

    def _build_field_aggregates(
        self,
        states: dict[str, _FieldAggState],
        *,
        scope: str,
    ) -> list[FieldSummaryAggregate]:
        summaries: list[FieldSummaryAggregate] = []
        for name in self._field_order:
            state = states.get(name)
            if state is None:
                continue
            tables_mapped = len(state.tables) if state.tables else 0
            sheets_mapped = len(state.sheets) if state.sheets else 0
            files_mapped = len(state.files) if state.files else 0
            summaries.append(
                FieldSummaryAggregate(
                    field=state.field,
                    label=state.label,
                    required=state.required,
                    mapped=state.mapped,
                    max_score=state.max_score,
                    tables_mapped=tables_mapped if scope in {"sheet", "file", "run"} else None,
                    sheets_mapped=sheets_mapped if scope in {"file", "run"} else None,
                    files_mapped=files_mapped if scope == "run" else None,
                )
            )
        return summaries

    @staticmethod
    def _build_validation_aggregate(state: _ValidationAggState) -> ValidationSummary:
        return ValidationSummary(
            rows_evaluated=state.rows_evaluated,
            issues_total=state.issues_total,
            issues_by_severity=dict(state.issues_by_severity),
            issues_by_code=dict(state.issues_by_code),
            issues_by_field=dict(state.issues_by_field),
            max_severity=state.max_severity,
        )

    def _ensure_field_states(self, state: _ScopeState) -> None:
        for name, info in self._field_catalog.items():
            state.field_states.setdefault(
                name,
                _FieldAggState(field=name, label=info.label, required=info.required),
            )


__all__ = ["SummaryAggregator"]
