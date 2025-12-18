from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from ade_engine.application.run_completion_report import RunCompletionReportBuilder
from ade_engine.infrastructure.settings import Settings
from ade_engine.models.run import RunStatus
from ade_engine.models.table import SourceColumn, TableRegion, TableResult


def test_run_completion_report_allows_hooks_to_filter_rows() -> None:
    """Hooks can legally filter rows post-validation; reporting must not crash."""

    builder = RunCompletionReportBuilder(input_file=Path("input.xlsx"), settings=Settings())

    source_columns = [
        SourceColumn(index=0, header="First Name", values=["Alice", "Bob", None, "Zoe"]),
        SourceColumn(index=1, header="Last Name", values=["Smith", "Jones", None, "Zeta"]),
        SourceColumn(index=2, header="Email", values=["alice@example.com", "bob.example.com", "no@example.com", "z@example.com"]),
    ]

    # Simulate a hook filtering the table down to 1 row, but keep the original
    # detected source columns (values for all 4 source rows).
    filtered_table = pl.DataFrame({"first_name": ["Alice"], "last_name": ["Smith"], "email": ["alice@example.com"]})

    builder.record_table(
        TableResult(
            sheet_name="Sheet1",
            sheet_index=0,
            table_index=0,
            source_region=TableRegion(header_row=1, first_col=1, last_row=5, last_col=len(source_columns)),
            source_columns=source_columns,
            table=filtered_table,
            row_count=filtered_table.height,
        )
    )

    payload = builder.build(
        run_status=RunStatus.SUCCEEDED,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        error=None,
        output_path=None,
        output_written=False,
    )

    table_summary = payload.workbooks[0].sheets[0].tables[0]
    assert table_summary.counts.cells is not None
    assert table_summary.counts.cells.total == 12
    assert table_summary.counts.cells.non_empty == 10
