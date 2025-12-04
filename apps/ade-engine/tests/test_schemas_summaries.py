from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ade_engine.schemas.summaries import (
    ColumnCounts,
    Counts,
    FieldCounts,
    RunSummary,
    ValidationSummary,
)


def _empty_counts() -> Counts:
    return Counts(
        rows={"total": 0, "empty": 0, "non_empty": 0},
        columns={
            "physical_total": 0,
            "physical_empty": 0,
            "physical_non_empty": 0,
            "distinct_headers": 0,
            "distinct_headers_mapped": 0,
            "distinct_headers_unmapped": 0,
        },
        fields={
            "total": 0,
            "required": 0,
            "mapped": 0,
            "unmapped": 0,
            "required_mapped": 0,
            "required_unmapped": 0,
        },
    )


def test_run_summary_defaults() -> None:
    summary = RunSummary(
        scope="run",
        id="run",
        parent_ids={"run_id": "123"},
        source={
            "run_id": "123",
            "workspace_id": None,
            "configuration_id": None,
            "engine_version": "test",
            "started_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        },
        counts=_empty_counts(),
        fields=[],
        columns=[],
        validation=ValidationSummary(),
        details={},
    )

    assert summary.schema_id == "ade.summary"
    assert summary.schema_version == "1.0.0"
    assert summary.counts.rows.total == 0
    assert summary.validation.issues_total == 0


def test_counts_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ColumnCounts(
            physical_total=0,
            physical_empty=0,
            physical_non_empty=0,
            distinct_headers=0,
            distinct_headers_mapped=0,
            distinct_headers_unmapped=0,
            unexpected=True,  # type: ignore[arg-type]
        )
