from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ade_engine.core.pipeline.summary_builder import SummaryAggregator
from ade_engine.core.types import (
    ColumnMap,
    ExtractedTable,
    MappedColumn,
    MappedTable,
    NormalizedTable,
    RunContext,
    RunPaths,
    RunStatus,
    UnmappedColumn,
    ValidationIssue,
)


def _run_context() -> RunContext:
    run_id = uuid4()
    return RunContext(
        run_id=run_id,
        metadata={
            "workspace_id": str(uuid4()),
            "configuration_id": str(uuid4()),
            "run_id": str(run_id),
            "build_id": str(uuid4()),
        },
        manifest=None,
        paths=RunPaths(
            input_dir=Path("input"),
            output_dir=Path("output"),
            logs_dir=Path("logs"),
        ),
        started_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _normalized_table(source_file: Path, sheet: str | None = None) -> NormalizedTable:
    extracted = ExtractedTable(
        source_file=source_file,
        source_sheet=sheet,
        table_index=0,
        header_row=["a", "b", "note"],
        data_rows=[["1", "2", ""], ["", "3", "note"]],
        header_row_index=1,
        first_data_row_index=2,
        last_data_row_index=3,
    )
    column_map = ColumnMap(
        mapped_columns=[
            MappedColumn(field="field_a", header="a", source_column_index=0, score=0.9, contributions=()),
            MappedColumn(field="field_b", header="b", source_column_index=1, score=0.8, contributions=(), is_required=True),
        ],
        unmapped_columns=[
            UnmappedColumn(header="note", source_column_index=2, output_header="raw_3"),
        ],
    )
    mapped = MappedTable(extracted=extracted, column_map=column_map)
    issues = [
        ValidationIssue(
            row_index=1,
            field="field_b",
            code="warn",
            severity="warning",
            message="sample",
        )
    ]
    return NormalizedTable(
        mapped=mapped,
        rows=extracted.data_rows,
        validation_issues=issues,
        output_sheet_name="Normalized",
    )


def test_summary_aggregator_builds_hierarchy():
    ctx = _run_context()
    ctx.completed_at = datetime(2024, 1, 1, 0, 10, tzinfo=timezone.utc)
    table = _normalized_table(Path("file1.xlsx"), sheet="Sheet1")

    aggregator = SummaryAggregator(run=ctx, manifest=None, engine_version="1.0.0", config_version="1.0.0")
    table_summary = aggregator.add_table(table)

    sheets, files, run_summary = aggregator.finalize(
        status=RunStatus.SUCCEEDED,
        failure=None,
        completed_at=ctx.completed_at,
        output_paths=["output/file.xlsx"],
        processed_files=["file1.xlsx"],
    )

    assert table_summary.counts.rows.total == 2
    assert table_summary.counts.columns.physical_total == 3
    assert sheets[0].counts.tables == {"total": 1}
    assert files[0].counts.tables == {"total": 1}
    assert run_summary.counts.tables == {"total": 1}
    assert run_summary.counts.columns.distinct_headers == 3
    assert run_summary.validation.issues_total == 1
    assert run_summary.details.get("processed_files") == ["file1.xlsx"]
