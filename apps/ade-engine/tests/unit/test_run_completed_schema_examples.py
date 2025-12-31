from __future__ import annotations

import pytest

from ade_engine.models.events import RunCompletedPayloadV1

RUN_COMPLETED_SUCCESS = {
    "schema_version": 1,
    "scope": "run",
    "execution": {
        "status": "succeeded",
        "started_at": "2025-01-01T00:00:00Z",
        "completed_at": "2025-01-01T00:00:00Z",
        "duration_ms": 0,
    },
    "evaluation": {
        "outcome": "success",
        "findings": [],
    },
    "counts": {
        "workbooks": 0,
        "sheets": 0,
        "tables": 0,
        "rows": {"total": 0, "empty": 0},
        "columns": {"total": 0, "empty": 0, "mapped": 0, "unmapped": 0},
        "fields": {"expected": 0, "detected": 0, "not_detected": 0},
    },
    "validation": {
        "rows_evaluated": 0,
        "issues_total": 0,
        "issues_by_severity": {},
        "max_severity": None,
    },
    "fields": [],
    "workbooks": [],
}

RUN_COMPLETED_FAILED_PARTIAL = {
    "schema_version": 1,
    "scope": "run",
    "execution": {
        "status": "failed",
        "started_at": "2025-01-01T00:00:00Z",
        "completed_at": "2025-01-01T00:00:00Z",
        "duration_ms": 0,
        "failure": {
            "stage": "run",
            "code": "engine_error",
            "message": "Engine failed after partial output.",
        },
    },
    "evaluation": {
        "outcome": "partial",
        "findings": [
            {
                "code": "partial_output",
                "severity": "warning",
                "message": "Partial output produced before failure.",
                "count": 1,
            }
        ],
    },
    "counts": {
        "workbooks": 0,
        "sheets": 0,
        "tables": 0,
        "rows": {"total": 0, "empty": 0},
        "columns": {"total": 0, "empty": 0, "mapped": 0, "unmapped": 0},
        "fields": {"expected": 0, "detected": 0, "not_detected": 0},
    },
    "validation": {
        "rows_evaluated": 0,
        "issues_total": 1,
        "issues_by_severity": {"warning": 1},
        "max_severity": "warning",
    },
    "fields": [],
    "workbooks": [],
}

@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(RUN_COMPLETED_SUCCESS, id="success"),
        pytest.param(RUN_COMPLETED_FAILED_PARTIAL, id="failed_partial"),
    ],
)
def test_run_completed_examples_validate_strict(payload: dict[str, object]) -> None:
    # Contract: strict validation, extra fields forbidden, stable invariants.
    model = RunCompletedPayloadV1.model_validate(payload, strict=True)

    # Important: when producing a strict payload for re-validation (e.g. before emitting to RunLogger),
    # do not drop null fields; `exclude_none=True` can remove required-but-nullable keys (like header.raw).
    roundtrip = model.model_dump(mode="python")
    RunCompletedPayloadV1.model_validate(roundtrip, strict=True)

    dumped = model.model_dump(mode="python", exclude_none=True)
    assert dumped.get("schema_version") == 1
    assert dumped.get("scope") == "run"
