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
                "valid_cells": 0,
                "occurrences": {"tables": 0, "columns": 0},
            },
            {
                "field": "first_name",
                "label": "First Name",
                "detected": True,
                "best_mapping_score": 1.0,
                "valid_cells": 7,
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
                                            "non_empty_cells": 12,
                                            "valid_cells": 8,
                                            "mapping": {
                                                "status": "unmapped",
                                                "unmapped_reason": "no_signal",
                                            },
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
    assert rows[1]["valid_cells"] == 7


def test_parse_run_table_columns() -> None:
    rows = parse_run_table_columns(_sample_payload())
    assert len(rows) == 2
    row0 = rows[0]
    assert row0["workbook_index"] == 0
    assert row0["sheet_name"] == "Sheet1"
    assert row0["mapping_status"] == "mapped"
    assert row0["mapped_field"] == "email"
    assert row0["non_empty_cells"] == 10
    assert (
        row0["valid_cells"] == 10
    )  # Fallback to non_empty_cells since valid_cells was missing/None

    row1 = rows[1]
    assert row1["workbook_index"] == 0
    assert row1["sheet_name"] == "Sheet1"
    assert row1["mapping_status"] == "unmapped"
    assert row1["mapped_field"] is None
    assert row1["non_empty_cells"] == 12
    assert row1["valid_cells"] == 8  # Explicitly parsed valid_cells


def test_as_str_accepts_uuid_values() -> None:
    value = uuid4()
    assert _as_str(value) == str(value)


def test_mapped_with_zero_valid_cells_stays_mapped() -> None:
    payload = _sample_payload()
    # Explicitly set valid_cells to 0 for the mapped column (index 0)
    payload["workbooks"][0]["sheets"][0]["tables"][0]["structure"]["columns"][0]["valid_cells"] = 0

    # Parse columns
    columns = parse_run_table_columns(payload)
    # The first column remains mapped even though it has no valid cells.
    assert columns[0]["mapping_status"] == "mapped"
    assert columns[0]["mapped_field"] == "email"
    assert columns[0]["mapping_score"] == 1.0
    assert columns[0]["mapping_method"] == "classifier"
    assert columns[0]["unmapped_reason"] is None

    # The second column (originally unmapped) remains unchanged
    assert columns[1]["mapping_status"] == "unmapped"

    # Parse metrics
    metrics = parse_run_metrics(payload)
    assert metrics is not None
    assert metrics["column_count_mapped"] == 2
    assert metrics["column_count_unmapped"] == 3
