from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ade_engine.schemas.run_summary import (
    RunSummaryBreakdowns,
    RunSummaryCore,
    RunSummaryRun,
    RunSummaryV1,
)


def _build_summary(**overrides):
    return RunSummaryV1(
        run=RunSummaryRun(
            id="run-1",
            status="succeeded",
            started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            **overrides,
        ),
        core=RunSummaryCore(),
        breakdowns=RunSummaryBreakdowns(),
    )


def test_run_summary_defaults():
    summary = _build_summary()

    assert summary.schema == "ade.run_summary/v1"
    assert summary.version == "1.0.0"
    assert summary.core.input_file_count == 0
    assert summary.core.issue_counts_by_severity == {}
    assert summary.breakdowns.by_file == []
    assert summary.breakdowns.by_field == []


def test_run_summary_forbids_extra_fields():
    with pytest.raises(ValidationError):
        RunSummaryCore(input_file_count=1, extra_field="nope")  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        RunSummaryRun(
            id="run-1",
            status="succeeded",
            started_at=datetime.now(tz=timezone.utc),
            unexpected=True,  # type: ignore[arg-type]
        )
