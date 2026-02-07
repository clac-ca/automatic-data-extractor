from __future__ import annotations

from uuid import uuid4

from ade_worker.worker import (
    _as_str,
    parse_run_fields,
    parse_run_metrics,
    parse_run_table_columns,
)


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "scope": "run",
        "evaluation": {
            "outcome": "partial",
            "findings": [
                {"severity": "warning"},
                {"severity": "error"},
                {"severity": "warning"},
            ],
        },
        "validation": {
            "issues_total": 0,
            "issues_by_severity": {"info": 0, "warning": 0, "error": 0},
            "max_severity": None,
        },
        "counts": {
            "workbooks": 1,
            "sheets": 2,
            "tables": 1,
            "rows": {"total": 28, "empty": 2},
            "columns": {"total": 5, "empty": 0, "mapped": 2, "unmapped": 3},
            "fields": {"expected": 3, "detected": 2, "not_detected": 1},
            "cells": {"total": 140, "non_empty": 120},
        },
        "fields": [
            {
                "field": "email",
                "label": "Email",
                "detected": False,
                "best_mapping_score": None,
                "occurrences": {"tables": 0, "columns": 0},
            },
            {
                "field": "first_name",
                "label": "First Name",
                "detected": True,
                "best_mapping_score": 1.0,
                "occurrences": {"tables": 1, "columns": 1},
            },
        ],
        "workbooks": [
            {
                "locator": {"workbook": {"index": 0, "name": "Book1.xlsx"}},
                "sheets": [
                    {
                        "locator": {"sheet": {"index": 0, "name": "Sheet1"}},
                        "tables": [
                            {
                                "locator": {"table": {"index": 0}},
                                "structure": {
                                    "columns": [
                                        {
                                            "index": 0,
                                            "header": {"raw": "Email", "normalized": "email"},
                                            "non_empty_cells": 10,
                                            "mapping": {
                                                "status": "mapped",
                                                "field": "email",
                                                "score": 1.0,
                                                "method": "classifier",
                                                "unmapped_reason": None,
                                            },
                                        },
                                        {
                                            "index": 1,
                                            "header": {"raw": "Notes", "normalized": "notes"},
                                            "non_empty_cells": 0,
                                            "mapping": {"status": "unknown"},
                                        },
                                    ]
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_parse_run_metrics() -> None:
    metrics = parse_run_metrics(_sample_payload())
    assert metrics is not None
    assert metrics["evaluation_outcome"] == "partial"
    assert metrics["evaluation_findings_total"] == 3
    assert metrics["evaluation_findings_warning"] == 2
    assert metrics["evaluation_findings_error"] == 1
    assert metrics["workbook_count"] == 1
    assert metrics["column_count_mapped"] == 2
    assert metrics["cell_count_non_empty"] == 120


def test_parse_run_fields() -> None:
    rows = parse_run_fields(_sample_payload())
    assert len(rows) == 2
    assert rows[0]["field"] == "email"
    assert rows[0]["detected"] is False
    assert rows[1]["field"] == "first_name"
    assert rows[1]["best_mapping_score"] == 1.0


def test_parse_run_table_columns() -> None:
    rows = parse_run_table_columns(_sample_payload())
    assert len(rows) == 1
    row = rows[0]
    assert row["workbook_index"] == 0
    assert row["sheet_name"] == "Sheet1"
    assert row["mapping_status"] == "mapped"
    assert row["mapped_field"] == "email"


def test_as_str_accepts_uuid_values() -> None:
    value = uuid4()
    assert _as_str(value) == str(value)
