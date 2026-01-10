"""Parse engine.run.completed payloads into run result rows."""

from __future__ import annotations

from typing import Any

SEVERITIES = ("info", "warning", "error")
MAPPING_STATUSES = ("mapped", "unmapped")


def _as_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _as_str(value: Any) -> str | None:
    if isinstance(value, str):
        candidate = value.strip()
        return candidate or None
    return None


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        candidate = value.strip()
        if candidate and candidate.lstrip("-").isdigit():
            try:
                return int(candidate)
            except ValueError:
                return None
    return None


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        try:
            return float(candidate)
        except ValueError:
            return None
    return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in {"1", "true", "yes", "y", "on"}:
            return True
        if candidate in {"0", "false", "no", "n", "off"}:
            return False
    return None


def _normalize_mapping_status(value: Any) -> str | None:
    status = _as_str(value)
    if status is None:
        return None
    status = status.lower()
    return status if status in MAPPING_STATUSES else None


def _count_findings(findings: list[Any]) -> dict[str, int]:
    counts = {severity: 0 for severity in SEVERITIES}
    for item in findings:
        data = _as_dict(item) or {}
        severity = _as_str(data.get("severity"))
        if severity is None:
            continue
        severity = severity.lower()
        if severity in counts:
            counts[severity] += 1
    return counts


def _metrics_has_values(metrics: dict[str, Any]) -> bool:
    return any(value is not None for value in metrics.values())


def parse_run_metrics(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    scope = _as_str(payload.get("scope"))
    if scope is not None and scope != "run":
        return None

    metrics: dict[str, Any] = {
        "evaluation_outcome": None,
        "evaluation_findings_total": None,
        "evaluation_findings_info": None,
        "evaluation_findings_warning": None,
        "evaluation_findings_error": None,
        "validation_issues_total": None,
        "validation_issues_info": None,
        "validation_issues_warning": None,
        "validation_issues_error": None,
        "validation_max_severity": None,
        "workbook_count": None,
        "sheet_count": None,
        "table_count": None,
        "row_count_total": None,
        "row_count_empty": None,
        "column_count_total": None,
        "column_count_empty": None,
        "column_count_mapped": None,
        "column_count_unmapped": None,
        "field_count_expected": None,
        "field_count_detected": None,
        "field_count_not_detected": None,
        "cell_count_total": None,
        "cell_count_non_empty": None,
    }

    evaluation = _as_dict(payload.get("evaluation")) or {}
    metrics["evaluation_outcome"] = _as_str(evaluation.get("outcome"))
    findings = evaluation.get("findings")
    if isinstance(findings, list):
        metrics["evaluation_findings_total"] = len(findings)
        counts = _count_findings(findings)
        metrics["evaluation_findings_info"] = counts["info"]
        metrics["evaluation_findings_warning"] = counts["warning"]
        metrics["evaluation_findings_error"] = counts["error"]

    validation = _as_dict(payload.get("validation")) or {}
    metrics["validation_issues_total"] = _as_int(validation.get("issues_total"))
    issues_by_severity = _as_dict(validation.get("issues_by_severity")) or {}
    metrics["validation_issues_info"] = _as_int(issues_by_severity.get("info"))
    metrics["validation_issues_warning"] = _as_int(issues_by_severity.get("warning"))
    metrics["validation_issues_error"] = _as_int(issues_by_severity.get("error"))
    metrics["validation_max_severity"] = _as_str(validation.get("max_severity"))

    counts = _as_dict(payload.get("counts")) or {}
    metrics["workbook_count"] = _as_int(counts.get("workbooks"))
    metrics["sheet_count"] = _as_int(counts.get("sheets"))
    metrics["table_count"] = _as_int(counts.get("tables"))

    rows = _as_dict(counts.get("rows")) or {}
    metrics["row_count_total"] = _as_int(rows.get("total"))
    metrics["row_count_empty"] = _as_int(rows.get("empty"))

    columns = _as_dict(counts.get("columns")) or {}
    metrics["column_count_total"] = _as_int(columns.get("total"))
    metrics["column_count_empty"] = _as_int(columns.get("empty"))
    metrics["column_count_mapped"] = _as_int(columns.get("mapped"))
    metrics["column_count_unmapped"] = _as_int(columns.get("unmapped"))

    fields = _as_dict(counts.get("fields")) or {}
    metrics["field_count_expected"] = _as_int(fields.get("expected"))
    metrics["field_count_detected"] = _as_int(fields.get("detected"))
    metrics["field_count_not_detected"] = _as_int(fields.get("not_detected"))

    cells = _as_dict(counts.get("cells")) or {}
    metrics["cell_count_total"] = _as_int(cells.get("total"))
    metrics["cell_count_non_empty"] = _as_int(cells.get("non_empty"))

    return metrics if _metrics_has_values(metrics) else None


def parse_run_fields(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    scope = _as_str(payload.get("scope"))
    if scope is not None and scope != "run":
        return []

    rows: list[dict[str, Any]] = []
    fields = payload.get("fields")
    if not isinstance(fields, list):
        return rows

    for item in fields:
        data = _as_dict(item)
        if not data:
            continue
        field_name = _as_str(data.get("field"))
        if not field_name:
            continue
        detected = _as_bool(data.get("detected"))
        if detected is None:
            continue
        occurrences = _as_dict(data.get("occurrences")) or {}
        rows.append(
            {
                "field": field_name,
                "label": _as_str(data.get("label")),
                "detected": detected,
                "best_mapping_score": _as_float(data.get("best_mapping_score")),
                "occurrences_tables": _as_int(occurrences.get("tables")) or 0,
                "occurrences_columns": _as_int(occurrences.get("columns")) or 0,
            }
        )

    return rows


def parse_run_table_columns(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    scope = _as_str(payload.get("scope"))
    if scope is not None and scope != "run":
        return []

    rows: list[dict[str, Any]] = []
    workbooks = payload.get("workbooks")
    if not isinstance(workbooks, list):
        return rows

    for workbook in workbooks:
        workbook_data = _as_dict(workbook) or {}
        workbook_locator = _as_dict(workbook_data.get("locator")) or {}
        workbook_info = _as_dict(workbook_locator.get("workbook")) or {}
        workbook_index = _as_int(workbook_info.get("index"))
        workbook_name = _as_str(workbook_info.get("name"))
        if workbook_index is None or not workbook_name:
            continue

        sheets = workbook_data.get("sheets")
        if not isinstance(sheets, list):
            continue
        for sheet in sheets:
            sheet_data = _as_dict(sheet) or {}
            sheet_locator = _as_dict(sheet_data.get("locator")) or {}
            sheet_info = _as_dict(sheet_locator.get("sheet")) or {}
            sheet_index = _as_int(sheet_info.get("index"))
            sheet_name = _as_str(sheet_info.get("name"))
            if sheet_index is None or not sheet_name:
                continue

            tables = sheet_data.get("tables")
            if not isinstance(tables, list):
                continue
            for table in tables:
                table_data = _as_dict(table) or {}
                table_locator = _as_dict(table_data.get("locator")) or {}
                table_info = _as_dict(table_locator.get("table")) or {}
                table_index = _as_int(table_info.get("index"))
                if table_index is None:
                    continue

                structure = _as_dict(table_data.get("structure")) or {}
                columns = structure.get("columns")
                if not isinstance(columns, list):
                    continue
                for column in columns:
                    column_data = _as_dict(column) or {}
                    column_index = _as_int(column_data.get("index"))
                    if column_index is None:
                        continue

                    mapping = _as_dict(column_data.get("mapping")) or {}
                    mapping_status = _normalize_mapping_status(mapping.get("status"))
                    if mapping_status is None:
                        continue

                    header = _as_dict(column_data.get("header")) or {}
                    rows.append(
                        {
                            "workbook_index": workbook_index,
                            "workbook_name": workbook_name,
                            "sheet_index": sheet_index,
                            "sheet_name": sheet_name,
                            "table_index": table_index,
                            "column_index": column_index,
                            "header_raw": _as_str(header.get("raw")),
                            "header_normalized": _as_str(header.get("normalized")),
                            "non_empty_cells": _as_int(column_data.get("non_empty_cells")) or 0,
                            "mapping_status": mapping_status,
                            "mapped_field": _as_str(mapping.get("field")),
                            "mapping_score": _as_float(mapping.get("score")),
                            "mapping_method": _as_str(mapping.get("method")),
                            "unmapped_reason": _as_str(mapping.get("unmapped_reason")),
                        }
                    )

    return rows


__all__ = ["parse_run_fields", "parse_run_metrics", "parse_run_table_columns"]
