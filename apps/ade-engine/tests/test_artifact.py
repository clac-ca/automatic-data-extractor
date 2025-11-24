from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.types import (
    ColumnMap,
    MappedColumn,
    MappedTable,
    NormalizedTable,
    RawTable,
    RunContext,
    RunError,
    RunErrorCode,
    RunPaths,
    RunPhase,
    RunStatus,
    UnmappedColumn,
    ValidationIssue,
)
from ade_engine.infra.artifact import FileArtifactSink
from ade_engine.schemas.manifest import ColumnsConfig, FieldConfig, HookCollection, ManifestV1, WriterConfig


def build_manifest() -> ManifestContext:
    manifest_dict = {
        "schema": "ade.manifest/v1",
        "version": "1.0.0",
        "name": "Test Config",
        "description": "",
        "script_api_version": 1,
        "columns": {
            "order": ["id", "email"],
            "fields": {
                "id": {"label": "ID", "module": "id", "required": True},
                "email": {"label": "Email", "module": "email"},
            },
        },
        "hooks": {},
        "writer": {},
        "extra": None,
    }
    manifest_model = ManifestV1(
        schema="ade.manifest/v1",
        version="1.0.0",
        name="Test Config",
        description="",
        script_api_version=1,
        columns=ColumnsConfig(
            order=["id", "email"],
            fields={
                "id": FieldConfig(label="ID", module="id", required=True),
                "email": FieldConfig(label="Email", module="email"),
            },
        ),
        hooks=HookCollection(),
        writer=WriterConfig(),
        extra=None,
    )
    return ManifestContext(raw_json=manifest_dict, model=manifest_model)


def build_run_context(tmp_path: Path) -> RunContext:
    paths = RunPaths(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
        artifact_path=tmp_path / "logs" / "artifact.json",
        events_path=tmp_path / "logs" / "events.ndjson",
    )
    return RunContext(
        run_id="run-123",
        metadata={"job_id": "job-1"},
        manifest=None,
        paths=paths,
        started_at=datetime(2024, 1, 1, 12, 0, 0),
    )


def build_normalized_table(tmp_path: Path) -> NormalizedTable:
    raw_table = RawTable(
        source_file=tmp_path / "input" / "data.xlsx",
        source_sheet="Sheet1",
        table_index=0,
        header_row=["ID", "Email"],
        data_rows=[["1", "a@example.com"], ["2", "b@example.com"]],
        header_row_index=2,
        first_data_row_index=3,
        last_data_row_index=4,
    )
    column_map = ColumnMap(
        mapped_columns=[
            MappedColumn(
                field="id",
                header="ID",
                source_column_index=0,
                score=0.9,
                contributions=(),
                is_required=True,
                is_satisfied=True,
            ),
            MappedColumn(
                field="email",
                header="Email",
                source_column_index=1,
                score=0.8,
                contributions=(),
            ),
        ],
        unmapped_columns=[
            UnmappedColumn(header="Notes", source_column_index=2, output_header="raw_notes"),
        ],
    )
    mapped_table = MappedTable(raw=raw_table, column_map=column_map)
    validation_issues = [
        ValidationIssue(
            row_index=3,
            field="email",
            code="invalid_format",
            severity="error",
            message="Invalid email",
            details={"value": "b@"},
        )
    ]
    return NormalizedTable(
        mapped=mapped_table,
        rows=[["1", "a@example.com", None], ["2", "b@example.com", "bad"]],
        validation_issues=validation_issues,
        output_sheet_name="Normalized",
    )


def test_file_artifact_sink_records_tables_and_success(tmp_path: Path) -> None:
    run = build_run_context(tmp_path)
    manifest = build_manifest()
    table = build_normalized_table(tmp_path)

    sink = FileArtifactSink(artifact_path=run.paths.artifact_path)
    sink.start(run, manifest)
    sink.record_table(table)
    run.completed_at = run.started_at + timedelta(seconds=5)
    sink.mark_success([run.paths.output_dir / "normalized.xlsx"])
    sink.note("Completed mapping", level="info", details={"tables": 1})
    sink.flush()

    artifact = json.loads(run.paths.artifact_path.read_text())
    assert artifact["schema"] == "ade.artifact/v1"
    assert artifact["run"]["status"] == RunStatus.SUCCEEDED
    assert artifact["run"]["outputs"] == ["normalized.xlsx"]
    assert artifact["tables"][0]["source_sheet"] == "Sheet1"
    assert artifact["tables"][0]["header"]["row_index"] == 2
    assert artifact["tables"][0]["mapped_columns"][0]["field"] == "id"
    assert artifact["tables"][0]["validation_issues"][0]["code"] == "invalid_format"
    assert artifact["notes"][0]["message"] == "Completed mapping"


def test_file_artifact_sink_records_failure(tmp_path: Path) -> None:
    run = build_run_context(tmp_path)
    manifest = build_manifest()

    sink = FileArtifactSink(artifact_path=run.paths.artifact_path)
    sink.start(run, manifest)
    sink.mark_failure(
        RunError(code=RunErrorCode.INPUT_ERROR, stage=RunPhase.EXTRACTING, message="Missing file"),
        details={"source_file": "missing.xlsx"},
    )
    sink.flush()

    artifact = json.loads(run.paths.artifact_path.read_text())
    assert artifact["run"]["status"] == RunStatus.FAILED
    assert artifact["run"]["error"]["code"] == RunErrorCode.INPUT_ERROR
    assert artifact["run"]["error"]["stage"] == RunPhase.EXTRACTING
    assert artifact["run"]["error"]["details"] == {"source_file": "missing.xlsx"}
