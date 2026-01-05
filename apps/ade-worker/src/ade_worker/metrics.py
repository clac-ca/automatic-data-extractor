"""Parse engine.run.completed payloads into run metrics rows."""

from __future__ import annotations

from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any] | None:
    return value if isinstance(value, list) else None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def extract_run_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    evaluation = _as_dict(payload.get("evaluation"))
    findings = _as_list(evaluation.get("findings"))
    findings_total = len(findings) if isinstance(findings, list) else None
    findings_by_severity = {"info": 0, "warning": 0, "error": 0}
    for finding in findings or []:
        if not isinstance(finding, dict):
            continue
        severity = finding.get("severity")
        if severity in findings_by_severity:
            findings_by_severity[severity] += 1

    validation = _as_dict(payload.get("validation"))
    issues_by_severity = _as_dict(validation.get("issues_by_severity"))
    issues_info = _coerce_int(issues_by_severity.get("info"))
    issues_warning = _coerce_int(issues_by_severity.get("warning"))
    issues_error = _coerce_int(issues_by_severity.get("error"))

    counts = _as_dict(payload.get("counts"))
    rows = _as_dict(counts.get("rows"))
    columns = _as_dict(counts.get("columns"))
    fields = _as_dict(counts.get("fields"))
    cells = _as_dict(counts.get("cells"))

    columns_mapped = _coerce_int(columns.get("mapped"))
    columns_unmapped = _coerce_int(columns.get("unmapped"))
    field_count_detected = _coerce_int(fields.get("detected"))
    field_count_not_detected = _coerce_int(fields.get("not_detected"))

    return {
        "evaluation_outcome": _coerce_str(evaluation.get("outcome")),
        "evaluation_findings_total": findings_total,
        "evaluation_findings_info": findings_by_severity["info"] if findings_total else None,
        "evaluation_findings_warning": findings_by_severity["warning"] if findings_total else None,
        "evaluation_findings_error": findings_by_severity["error"] if findings_total else None,
        "validation_issues_total": _coerce_int(validation.get("issues_total")),
        "validation_issues_info": issues_info,
        "validation_issues_warning": issues_warning,
        "validation_issues_error": issues_error,
        "validation_max_severity": _coerce_str(validation.get("max_severity")),
        "workbook_count": _coerce_int(counts.get("workbooks")),
        "sheet_count": _coerce_int(counts.get("sheets")),
        "table_count": _coerce_int(counts.get("tables")),
        "row_count_total": _coerce_int(rows.get("total")),
        "row_count_empty": _coerce_int(rows.get("empty")),
        "column_count_total": _coerce_int(columns.get("total")),
        "column_count_empty": _coerce_int(columns.get("empty")),
        "column_count_mapped": columns_mapped,
        "column_count_unmapped": columns_unmapped,
        "field_count_expected": _coerce_int(fields.get("expected")),
        "field_count_detected": field_count_detected,
        "field_count_not_detected": field_count_not_detected,
        "cell_count_total": _coerce_int(cells.get("total")),
        "cell_count_non_empty": _coerce_int(cells.get("non_empty")),
    }


def extract_run_fields(fields_payload: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for entry in fields_payload:
        if not isinstance(entry, dict):
            continue
        field_name = _coerce_str(entry.get("field"))
        if not field_name or field_name in seen:
            continue
        seen.add(field_name)

        occurrences = entry.get("occurrences")
        if not isinstance(occurrences, dict):
            occurrences = {}

        rows.append(
            {
                "field": field_name,
                "label": _coerce_str(entry.get("label")),
                "detected": True if entry.get("detected") is True else False,
                "best_mapping_score": _coerce_float(entry.get("best_mapping_score")),
                "occurrences_tables": _coerce_int(occurrences.get("tables")) or 0,
                "occurrences_columns": _coerce_int(occurrences.get("columns")) or 0,
            }
        )

    return rows


def extract_run_columns(workbooks: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for workbook in workbooks:
        if not isinstance(workbook, dict):
            continue
        locator = workbook.get("locator")
        if not isinstance(locator, dict):
            continue
        wb_locator = locator.get("workbook")
        if not isinstance(wb_locator, dict):
            continue
        workbook_index = _coerce_int(wb_locator.get("index"))
        workbook_name = _coerce_str(wb_locator.get("name"))
        if workbook_index is None or workbook_name is None:
            continue

        sheets = workbook.get("sheets")
        if not isinstance(sheets, list):
            continue

        for sheet in sheets:
            if not isinstance(sheet, dict):
                continue
            sheet_locator = sheet.get("locator")
            if not isinstance(sheet_locator, dict):
                continue
            sheet_ref = sheet_locator.get("sheet")
            if not isinstance(sheet_ref, dict):
                continue
            sheet_index = _coerce_int(sheet_ref.get("index"))
            sheet_name = _coerce_str(sheet_ref.get("name"))
            if sheet_index is None or sheet_name is None:
                continue

            tables = sheet.get("tables")
            if not isinstance(tables, list):
                continue

            for table in tables:
                if not isinstance(table, dict):
                    continue
                table_locator = table.get("locator")
                if not isinstance(table_locator, dict):
                    continue
                table_index = _coerce_int(table_locator.get("table_index"))
                if table_index is None:
                    continue

                columns = table.get("columns")
                if not isinstance(columns, list):
                    continue

                for column in columns:
                    if not isinstance(column, dict):
                        continue
                    column_index = _coerce_int(column.get("index"))
                    if column_index is None:
                        continue

                    mapping = column.get("mapping")
                    if not isinstance(mapping, dict):
                        mapping = {}

                    rows.append(
                        {
                            "workbook_index": workbook_index,
                            "workbook_name": workbook_name,
                            "sheet_index": sheet_index,
                            "sheet_name": sheet_name,
                            "table_index": table_index,
                            "column_index": column_index,
                            "header_raw": _coerce_str(column.get("header_raw")),
                            "header_normalized": _coerce_str(column.get("header_normalized")),
                            "non_empty_cells": _coerce_int(column.get("non_empty_cells")) or 0,
                            "mapping_status": _coerce_str(mapping.get("status")) or "unknown",
                            "mapped_field": _coerce_str(mapping.get("field")),
                            "mapping_score": _coerce_float(mapping.get("score")),
                            "mapping_method": _coerce_str(mapping.get("method")),
                            "unmapped_reason": _coerce_str(mapping.get("reason")),
                        }
                    )

    return rows


__all__ = ["extract_run_metrics", "extract_run_fields", "extract_run_columns"]
