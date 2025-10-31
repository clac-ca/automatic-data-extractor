"""Manifest-driven pipeline execution for Jobs worker."""

from __future__ import annotations

import inspect
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from openpyxl import load_workbook

from .loader import (
    ConfigPackageLoader,
    LoadedColumnModule,
    LoadedHookModule,
    LoadedRowModule,
)


@dataclass(slots=True)
class SheetData:
    name: str
    rows: list[list[Any]]


@dataclass(slots=True)
class TableData:
    id: str
    sheet_name: str
    source_file: str
    header_row: int
    header_values: list[Any]
    data_rows: list[list[Any]]


@dataclass(slots=True)
class ColumnPlugin:
    field_name: str
    path: str
    detectors: list[Callable[..., Any]]
    transform: Callable[..., Any] | None
    validate: Callable[..., Any] | None
    field_meta: dict[str, Any]


@dataclass(slots=True)
class RowPlugin:
    path: str
    detectors: list[Callable[..., Any]]


@dataclass(slots=True)
class ColumnAssignment:
    column_index: int
    header: str | None
    raw_values: list[Any]
    target_field: str | None
    confidence: float
    contributors: list[dict[str, Any]]
    transformed_values: list[Any]
    warnings: list[str]
    issues: list[dict[str, Any]]


@dataclass(slots=True)
class PipelineResult:
    table: TableData
    tables_summary: list[dict[str, Any]]
    assignments: list[ColumnAssignment]
    diagnostics: list[dict[str, Any]]
    pass_summaries: list[dict[str, Any]]
    artifact_template: dict[str, Any]
    sheet_title: str


class PipelineRunner:
    """Execute manifest-driven pipeline inside the worker subprocess."""

    def __init__(
        self,
        *,
        config_dir: Path,
        manifest: dict[str, Any],
        job_context: dict[str, Any],
        input_paths: list[str],
    ) -> None:
        self._config_dir = config_dir.resolve()
        self._manifest = manifest
        self._job_context = job_context
        self._env = manifest.get("env") or {}
        self._loader = ConfigPackageLoader(self._config_dir)
        self._diagnostics: list[dict[str, Any]] = []
        self._hooks: dict[str, list[LoadedHookModule]] = {}
        self._row_plugins: list[RowPlugin] = []
        self._column_plugins: list[ColumnPlugin] = []
        self._column_plugins_by_field: dict[str, ColumnPlugin] = {}
        self._input_paths = [Path(path).resolve() for path in input_paths]
        self._artifact_stub: dict[str, Any] = {"passes": []}
        writer_defaults = (
            manifest.get("engine", {}).get("writer") if isinstance(manifest.get("engine"), dict) else {}
        ) or {}
        self._sheet_title = str(writer_defaults.get("output_sheet") or "Normalized")
        self._sample_size = 8

    def execute(self) -> PipelineResult:
        """Run row detection, mapping, transform, and validation passes."""

        self._prime_modules()

        self._run_hook_group("on_job_start", artifact=self._artifact_stub, stage="on_job_start")

        sheets, source_file = self._load_sheet_data()
        tables_summary, table_data = self._detect_tables(sheets, source_file)
        detect_summary = {
            "name": "detect_tables",
            "status": "succeeded",
            "summary": {"tables": tables_summary},
        }
        self._artifact_stub["passes"].append(detect_summary)
        self._run_hook_group("on_after_extract", artifact=self._artifact_stub, stage="on_after_extract")

        assignments, mapping_summary = self._map_columns(table_data)
        self._artifact_stub["passes"].append(mapping_summary)
        self._run_hook_group("after_mapping", artifact=self._artifact_stub, stage="after_mapping")

        transform_summary = self._transform_columns(assignments, table_data)
        self._artifact_stub["passes"].append(transform_summary)
        self._run_hook_group("after_transform", artifact=self._artifact_stub, stage="after_transform")

        validate_summary = self._validate_columns(assignments, table_data)
        self._artifact_stub["passes"].append(validate_summary)
        self._run_hook_group("after_validate", artifact=self._artifact_stub, stage="after_validate")

        return PipelineResult(
            table=table_data,
            tables_summary=tables_summary,
            assignments=assignments,
            diagnostics=self._diagnostics,
            pass_summaries=list(self._artifact_stub["passes"]),
            artifact_template={"passes": deepcopy(self._artifact_stub["passes"])},
            sheet_title=self._sheet_title,
        )

    def run_job_end(self, artifact: dict[str, Any]) -> None:
        """Execute job end hooks once the worker has built the artifact."""

        self._run_hook_group("on_job_end", artifact=artifact, stage="on_job_end")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prime_modules(self) -> None:
        try:
            loaded_columns = self._loader.load_column_modules(self._manifest)
            hooks = self._loader.load_hook_modules(self._manifest)
            rows = self._loader.load_row_type_modules()
        except Exception as exc:  # pragma: no cover - defensive
            self._add_diagnostic(
                level="error",
                code="runtime.module_import_error",
                message=str(exc),
            )
            raise

        columns_meta = (self._manifest.get("columns") or {}).get("meta", {}) or {}
        self._column_plugins = []
        for item in loaded_columns:
            detectors = [
                function
                for name, function in inspect.getmembers(item.module, inspect.isfunction)
                if name.startswith("detect_")
            ]
            transform = getattr(item.module, "transform", None)
            validate = getattr(item.module, "validate", None)
            plugin = ColumnPlugin(
                field_name=item.field_name,
                path=item.path,
                detectors=detectors,
                transform=transform,
                validate=validate,
                field_meta=columns_meta.get(item.field_name, {}),
            )
            self._column_plugins.append(plugin)
            self._column_plugins_by_field[item.field_name] = plugin

        self._row_plugins = []
        for row_module in rows:
            detectors = [
                function
                for name, function in inspect.getmembers(row_module.module, inspect.isfunction)
                if name.startswith("detect_")
            ]
            if detectors:
                self._row_plugins.append(RowPlugin(path=row_module.path, detectors=detectors))

        self._hooks = hooks

    def _load_sheet_data(self) -> tuple[list[SheetData], str]:
        if self._input_paths:
            primary = self._input_paths[0]
            if not primary.exists():
                raise FileNotFoundError(f"Input spreadsheet not found at {primary}")
            workbook = load_workbook(primary, data_only=True)
            sheets: list[SheetData] = []
            for worksheet in workbook.worksheets:
                rows: list[list[Any]] = []
                for row in worksheet.iter_rows(values_only=True):
                    rows.append([cell for cell in row])
                sheets.append(SheetData(name=worksheet.title, rows=rows))
            return sheets or [SheetData(name="Sheet1", rows=[])], primary.name

        # Fallback: synthesize a single sheet using manifest column labels.
        columns = self._manifest.get("columns") or {}
        order = list(columns.get("order") or [])
        meta = columns.get("meta") or {}
        header = [str(meta.get(field, {}).get("label") or field) for field in order]
        return [SheetData(name="Sheet1", rows=[header])], "generated"

    def _detect_tables(self, sheets: list[SheetData], source_file: str) -> tuple[list[dict[str, Any]], TableData]:
        tables_summary: list[dict[str, Any]] = []
        primary_table: TableData | None = None

        for sheet in sheets:
            if not sheet.rows:
                sheet.rows.append([])

            header_row = self._find_header_row(sheet, source_file)
            header_values = sheet.rows[header_row - 1] if 0 <= header_row - 1 < len(sheet.rows) else []
            data_rows = sheet.rows[header_row:] if header_row < len(sheet.rows) else []
            table_id = f"{sheet.name or 'Sheet'}-table-1"

            table = TableData(
                id=table_id,
                sheet_name=sheet.name,
                source_file=source_file,
                header_row=header_row,
                header_values=list(header_values),
                data_rows=[list(row) for row in data_rows],
            )
            if primary_table is None:
                primary_table = table

            tables_summary.append(
                {
                    "id": table_id,
                    "sheet_name": sheet.name,
                    "source_file": source_file,
                    "header_row": header_row,
                    "data_row_start": header_row + 1,
                    "row_count": len(table.data_rows),
                    "column_count": len(table.header_values),
                    "header": [self._stringify(value) for value in table.header_values],
                }
            )

        if primary_table is None:
            # Guaranteed to exist because we populate fallback rows, but guard defensively.
            primary_table = TableData(
                id="Sheet1-table-1",
                sheet_name="Sheet1",
                source_file=source_file,
                header_row=1,
                header_values=[],
                data_rows=[],
            )

        return tables_summary, primary_table

    def _find_header_row(self, sheet: SheetData, source_file: str) -> int:
        best_index = 1
        best_score = float("-inf")

        for row_index, row_values in enumerate(sheet.rows, start=1):
            if self._is_empty_row(row_values):
                continue
            scores = self._evaluate_row_detectors(
                row_index=row_index,
                row_values=row_values,
                sheet_name=sheet.name,
                source_file=source_file,
            )
            header_score = scores.get("header", 0.0)
            if header_score > best_score:
                best_score = header_score
                best_index = row_index

        return max(best_index, 1)

    def _evaluate_row_detectors(
        self,
        *,
        row_index: int,
        row_values: list[Any],
        sheet_name: str,
        source_file: str,
    ) -> dict[str, float]:
        if not self._row_plugins:
            return {}

        scores: dict[str, float] = {}
        context = {
            "job_id": self._job_context.get("job_id"),
            "source_file": source_file,
            "sheet_name": sheet_name,
            "row_index": row_index,
            "row_values_sample": row_values[: self._sample_size],
            "manifest": self._manifest,
            "env": self._env,
            "artifact": self._artifact_stub,
        }

        for plugin in self._row_plugins:
            for detector in plugin.detectors:
                try:
                    result = self._invoke(detector, **context)
                except Exception as exc:  # pragma: no cover - defensive
                    self._add_diagnostic(
                        level="error",
                        code="runtime.row_detector.exception",
                        message=str(exc),
                        path=f"{plugin.path}:{detector.__name__}",
                        stage="detect_tables",
                    )
                    continue

                for label, delta in (result or {}).get("scores", {}).items():
                    try:
                        value = float(delta)
                    except (TypeError, ValueError):
                        continue
                    scores[label] = scores.get(label, 0.0) + value

        return scores

    def _map_columns(self, table: TableData) -> tuple[list[ColumnAssignment], dict[str, Any]]:
        columns_section = self._manifest.get("columns") or {}
        order: list[str] = list(columns_section.get("order") or [])
        meta: dict[str, dict[str, Any]] = columns_section.get("meta") or {}
        min_confidence = float(
            self._manifest.get("engine", {}).get("defaults", {}).get("min_mapping_confidence", 0.0)
        )

        column_values: list[ColumnAssignment] = []
        header_values = table.header_values or []
        row_count = len(table.data_rows)
        for index, header_value in enumerate(header_values, start=1):
            values: list[Any] = []
            for row in table.data_rows:
                value = row[index - 1] if index - 1 < len(row) else None
                values.append(value)

            assignment = ColumnAssignment(
                column_index=index,
                header=self._stringify(header_value),
                raw_values=values,
                target_field=None,
                confidence=0.0,
                contributors=[],
                transformed_values=list(values),
                warnings=[],
                issues=[],
            )

            scores: dict[str, float] = {}
            contributors: list[dict[str, Any]] = []
            column_context = {
                "job_id": self._job_context.get("job_id"),
                "source_file": table.source_file,
                "sheet_name": table.sheet_name,
                "table": self._table_context(table),
                "column_index": index,
                "header": assignment.header,
                "values_sample": assignment.raw_values[: self._sample_size],
                "manifest": self._manifest,
                "env": self._env,
                "job_context": self._job_context,
            }

            for plugin in self._column_plugins:
                column_context["field_name"] = plugin.field_name
                column_context["field_meta"] = plugin.field_meta
                for detector in plugin.detectors:
                    try:
                        result = self._invoke(detector, **column_context)
                    except Exception as exc:  # pragma: no cover - defensive
                        self._add_diagnostic(
                            level="error",
                            code="runtime.column_detector.exception",
                            message=str(exc),
                            path=f"{plugin.path}:{detector.__name__}",
                            stage="map_columns",
                        )
                        continue
                    for target, delta in (result or {}).get("scores", {}).items():
                        try:
                            value = float(delta)
                        except (TypeError, ValueError):
                            continue
                        scores[target] = scores.get(target, 0.0) + value
                        contributors.append(
                            {
                                "target": target,
                                "delta": value,
                                "rule": f"{plugin.path}:{detector.__name__}",
                            }
                        )

            if scores:
                best_score = max(scores.values())
                candidates = [field for field, score in scores.items() if score == best_score]
                selected_field = self._select_best_field(candidates, assignment.header, meta, order)
                if selected_field and best_score >= min_confidence:
                    assignment.target_field = selected_field
                    assignment.confidence = best_score
                    assignment.contributors = [
                        contributor
                        for contributor in contributors
                        if contributor["target"] == selected_field
                    ]

            column_values.append(assignment)

        summary = {
            "name": "map_columns",
            "status": "succeeded",
            "summary": {
                "table_id": table.id,
                "assignments": [
                    {
                        "column_index": assignment.column_index,
                        "raw_header": assignment.header,
                        "target_field": assignment.target_field,
                        "confidence": assignment.confidence,
                        "contributors": assignment.contributors,
                    }
                    for assignment in column_values
                ],
                "unmapped_columns": [
                    {
                        "column_index": assignment.column_index,
                        "raw_header": assignment.header,
                    }
                    for assignment in column_values
                    if assignment.target_field is None
                ],
            },
        }
        return column_values, summary

    def _transform_columns(self, assignments: list[ColumnAssignment], table: TableData) -> dict[str, Any]:
        for assignment in assignments:
            if not assignment.target_field:
                continue
            plugin = self._column_plugins_by_field.get(assignment.target_field)
            if plugin is None or plugin.transform is None:
                continue

            context = {
                "job_id": self._job_context.get("job_id"),
                "source_file": table.source_file,
                "sheet_name": table.sheet_name,
                "table": self._table_context(table),
                "column_index": assignment.column_index,
                "header": assignment.header,
                "values": list(assignment.transformed_values),
                "field_name": assignment.target_field,
                "field_meta": plugin.field_meta,
                "manifest": self._manifest,
                "env": self._env,
                "job_context": self._job_context,
            }
            try:
                result = self._invoke(plugin.transform, **context) or {}
            except Exception as exc:  # pragma: no cover - defensive
                self._add_diagnostic(
                    level="error",
                    code="runtime.transform.exception",
                    message=str(exc),
                    path=f"{plugin.path}:transform",
                    stage="transform_values",
                )
                continue

            values = list(result.get("values", assignment.transformed_values))
            assignment.transformed_values = values

            warnings = result.get("warnings") or []
            if isinstance(warnings, (str, bytes)):
                warnings = [warnings]
            assignment.warnings = [self._stringify(item) for item in warnings if item]

        summary = {
            "name": "transform_values",
            "status": "succeeded",
            "summary": {
                "fields": [
                    {
                        "field": assignment.target_field,
                        "warnings": assignment.warnings,
                    }
                    for assignment in assignments
                    if assignment.target_field
                ]
            },
        }
        return summary

    def _validate_columns(self, assignments: list[ColumnAssignment], table: TableData) -> dict[str, Any]:
        total_errors = 0
        total_warnings = 0

        for assignment in assignments:
            if not assignment.target_field:
                continue
            plugin = self._column_plugins_by_field.get(assignment.target_field)
            if plugin is None or plugin.validate is None:
                continue

            context = {
                "job_id": self._job_context.get("job_id"),
                "source_file": table.source_file,
                "sheet_name": table.sheet_name,
                "table": self._table_context(table),
                "column_index": assignment.column_index,
                "header": assignment.header,
                "values": list(assignment.transformed_values),
                "field_name": assignment.target_field,
                "field_meta": plugin.field_meta,
                "manifest": self._manifest,
                "env": self._env,
                "job_context": self._job_context,
            }
            try:
                result = self._invoke(plugin.validate, **context) or {}
            except Exception as exc:  # pragma: no cover - defensive
                self._add_diagnostic(
                    level="error",
                    code="runtime.validate.exception",
                    message=str(exc),
                    path=f"{plugin.path}:validate",
                    stage="validate_values",
                )
                continue

            issues = result.get("issues") or []
            normalized_issues: list[dict[str, Any]] = []
            for issue in issues:
                if isinstance(issue, dict):
                    entry = issue.copy()
                else:
                    entry = {"message": self._stringify(issue)}
                entry.setdefault("severity", "error")
                normalized_issues.append(entry)
                if entry["severity"] == "warning":
                    total_warnings += 1
                else:
                    total_errors += 1
            assignment.issues = normalized_issues

        summary = {
            "name": "validate_values",
            "status": "succeeded",
            "summary": {
                "total_errors": total_errors,
                "total_warnings": total_warnings,
                "fields": [
                    {
                        "field": assignment.target_field,
                        "issue_count": len(assignment.issues),
                    }
                    for assignment in assignments
                    if assignment.target_field
                ],
            },
        }
        return summary

    def _run_hook_group(self, name: str, *, artifact: dict[str, Any], stage: str) -> None:
        for hook in self._hooks.get(name, []):
            run_fn = getattr(hook.module, "run", None)
            if not callable(run_fn):
                self._add_diagnostic(
                    level="warning",
                    code="runtime.hook.missing_run",
                    message=f"Hook {hook.path} does not define run()",
                    path=hook.path,
                    stage=stage,
                )
                continue
            context = {
                "job_context": self._job_context,
                "manifest": self._manifest,
                "env": self._env,
                "artifact": artifact,
            }
            try:
                self._invoke(run_fn, **context)
            except Exception as exc:  # pragma: no cover - defensive
                self._add_diagnostic(
                    level="error",
                    code="runtime.hook.exception",
                    message=str(exc),
                    path=f"{hook.path}:run",
                    stage=stage,
                )

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _invoke(self, func: Callable[..., Any], **context: Any) -> Any:
        signature = None
        try:
            signature = inspect.signature(func)
        except (TypeError, ValueError):
            return func(**context)

        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
        )
        bound_arguments: dict[str, Any] = {}
        for name, parameter in signature.parameters.items():
            if name == "self":
                continue
            if parameter.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
                continue
            if name in context:
                bound_arguments[name] = context[name]
            elif parameter.default is inspect._empty and parameter.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            ):
                raise TypeError(f"Missing argument {name} for function {func.__name__}")
        if accepts_kwargs:
            for key, value in context.items():
                if key not in bound_arguments:
                    bound_arguments[key] = value
        return func(**bound_arguments)

    def _table_context(self, table: TableData) -> dict[str, Any]:
        return {
            "id": table.id,
            "sheet_name": table.sheet_name,
            "header_row": table.header_row,
            "data_row_start": table.header_row + 1,
            "row_count": len(table.data_rows),
            "column_count": len(table.header_values),
        }

    def _select_best_field(
        self,
        candidates: list[str],
        header: str | None,
        meta: dict[str, dict[str, Any]],
        order: list[str],
    ) -> str | None:
        valid_candidates = [field for field in candidates if field in order]
        if not valid_candidates:
            return None

        header_normalized = (header or "").strip().lower()
        if header_normalized:
            for field in valid_candidates:
                label = str(meta.get(field, {}).get("label") or field).strip().lower()
                if label == header_normalized:
                    return field
            for field in valid_candidates:
                synonyms = [str(value).strip().lower() for value in meta.get(field, {}).get("synonyms", [])]
                if header_normalized in synonyms:
                    return field

        # Fall back to the candidate that appears first in manifest order.
        for field in order:
            if field in valid_candidates:
                return field

        return valid_candidates[0]

    @staticmethod
    def _stringify(value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _is_empty_row(row: list[Any]) -> bool:
        return all(value in (None, "") for value in row)

    def _add_diagnostic(
        self,
        *,
        level: str,
        code: str,
        message: str,
        path: str | None = None,
        stage: str | None = None,
    ) -> None:
        diagnostic = {
            "level": level,
            "code": code,
            "message": message,
        }
        if path:
            diagnostic["path"] = path
        if stage:
            diagnostic["stage"] = stage
        self._diagnostics.append(diagnostic)


__all__ = ["PipelineResult", "PipelineRunner", "ColumnAssignment"]
