from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.types import (
    ColumnMap,
    MappedColumn,
    MappedTable,
    NormalizedTable,
    RawTable,
    RunContext,
    RunPaths,
    RunStatus,
    UnmappedColumn,
)
from ade_engine.infra.artifact import FileArtifactSink
from ade_engine.infra.telemetry import FileEventSink, PipelineLogger
from ade_engine.schemas.manifest import ColumnsConfig, FieldConfig, HookCollection, ManifestV1, WriterConfig


def build_run_context(tmp_path: Path) -> RunContext:
    paths = RunPaths(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
        artifact_path=tmp_path / "logs" / "artifact.json",
        events_path=tmp_path / "logs" / "events.ndjson",
    )
    return RunContext(
        run_id="run-456",
        metadata={"job_id": "job-1", "config_id": "cfg-1"},
        manifest=None,
        paths=paths,
        started_at=datetime(2024, 1, 1, 12, 0, 0),
    )


def build_manifest() -> ManifestContext:
    manifest_model = ManifestV1(
        schema="ade.manifest/v1",
        version="1.0.0",
        name="Telemetry Config",
        description="",
        script_api_version=1,
        columns=ColumnsConfig(
            order=["id"],
            fields={"id": FieldConfig(label="ID", module="id", required=True)},
        ),
        hooks=HookCollection(),
        writer=WriterConfig(),
        extra=None,
    )
    return ManifestContext(
        raw_json=manifest_model.model_dump(mode="json"),
        model=manifest_model,
    )


def build_table(tmp_path: Path) -> NormalizedTable:
    raw_table = RawTable(
        source_file=tmp_path / "input" / "data.xlsx",
        source_sheet="Sheet1",
        table_index=0,
        header_row=["ID"],
        data_rows=[["1"], ["2"]],
        header_row_index=1,
        first_data_row_index=2,
        last_data_row_index=3,
    )
    column_map = ColumnMap(
        mapped_columns=[
            MappedColumn(
                field="id",
                header="ID",
                source_column_index=0,
                score=1.0,
                contributions=(),
                is_required=True,
                is_satisfied=True,
            )
        ],
        unmapped_columns=[UnmappedColumn(header="Extra", source_column_index=1, output_header="raw_extra")],
    )
    mapped_table = MappedTable(raw=raw_table, column_map=column_map)
    return NormalizedTable(
        mapped=mapped_table,
        rows=[["1", None], ["2", None]],
        validation_issues=[],
        output_sheet_name="Normalized",
    )


def test_file_event_sink_writes_ndjson(tmp_path: Path) -> None:
    run = build_run_context(tmp_path)
    sink = FileEventSink(path=run.paths.events_path, min_level="info")

    sink.log("run_started", run=run, level="info", phase="initialization")
    sink.log("debug_event", run=run, level="debug", detail=True)
    sink.log("pipeline_transition", run=run, level="warning", phase="mapping")

    lines = run.paths.events_path.read_text().strip().split("\n")
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["schema"] == "ade.telemetry/run-event.v1"
    assert first["run_id"] == "run-456"
    assert first["event"]["event"] == "run_started"
    assert first["metadata"] == run.metadata


def test_pipeline_logger_records_notes_and_tables(tmp_path: Path) -> None:
    run = build_run_context(tmp_path)
    manifest = build_manifest()
    table = build_table(tmp_path)

    artifact_sink = FileArtifactSink(artifact_path=run.paths.artifact_path)
    artifact_sink.start(run, manifest)
    event_sink = FileEventSink(path=run.paths.events_path)

    logger = PipelineLogger(run=run, artifact_sink=artifact_sink, event_sink=event_sink)
    logger.note("Started run", level="info")
    logger.transition("mapping", file_count=1)
    logger.record_table(table)
    artifact_sink.mark_success([run.paths.output_dir / "normalized.xlsx"])
    artifact_sink.flush()

    artifact = json.loads(run.paths.artifact_path.read_text())
    events = run.paths.events_path.read_text().strip().split("\n")

    assert artifact["notes"][0]["message"] == "Started run"
    assert artifact["tables"][0]["source_file"].endswith("data.xlsx")
    assert len(events) == 3
    assert json.loads(events[1])["event"]["event"] == "pipeline_transition"
    assert json.loads(events[2])["event"]["event"] == "table_completed"
