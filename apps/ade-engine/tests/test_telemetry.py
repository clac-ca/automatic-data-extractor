from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ade_engine.config.manifest_context import ManifestContext
from ade_engine.core.types import (
    ColumnMap,
    MappedColumn,
    MappedTable,
    NormalizedTable,
    ExtractedTable,
    RunContext,
    RunPaths,
    UnmappedColumn,
)
from ade_engine.infra.event_emitter import EngineEventEmitter
from ade_engine.infra.telemetry import FileEventSink
from ade_engine.schemas.manifest import ColumnsConfig, FieldConfig, HookCollection, ManifestV1, WriterConfig
from ade_engine.schemas.telemetry import AdeEvent


def build_run_context(tmp_path: Path) -> RunContext:
    paths = RunPaths(
        input_file=tmp_path / "input" / "data.xlsx",
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
    )
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    return RunContext(
        run_id=uuid4(),
        metadata={"run_id": "run-1", "config_id": "cfg-1"},
        manifest=None,
        paths=paths,
        started_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


def build_manifest() -> ManifestContext:
    manifest_model = ManifestV1(
        schema="ade.manifest/v1",
        version="1.0.0",
        name="Telemetry Config",
        description="",
        script_api_version=3,
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
    raw_table = ExtractedTable(
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
    mapped_table = MappedTable(extracted=raw_table, column_map=column_map)
    return NormalizedTable(
        mapped=mapped_table,
        rows=[["1", None], ["2", None]],
        validation_issues=[],
        output_sheet_name="Normalized",
    )


def test_file_event_sink_writes_ndjson(tmp_path: Path) -> None:
    run = build_run_context(tmp_path)
    path = run.paths.logs_dir / "events.ndjson"
    sink = FileEventSink(path=path, min_level="info")

    info_event = AdeEvent(
        type="console.line",
        created_at=datetime.now(timezone.utc),
        run_id=run.run_id,
        payload={"scope": "run", "stream": "stdout", "level": "info", "message": "started"},
    )
    debug_event = AdeEvent(
        type="console.line",
        created_at=datetime.now(timezone.utc),
        run_id=run.run_id,
        payload={"scope": "run", "stream": "stdout", "level": "debug", "message": "verbose"},
    )

    sink.emit(info_event)
    sink.emit(debug_event)

    lines = path.read_text().strip().split("\n")
    assert len(lines) == 1

    first = json.loads(lines[0])
    assert first["run_id"] == str(run.run_id)
    assert first["payload"]["message"] == "started"


def test_event_emitter_records_events(tmp_path: Path) -> None:
    run = build_run_context(tmp_path)
    manifest = build_manifest()
    table = build_table(tmp_path)

    event_sink = FileEventSink(path=run.paths.logs_dir / "events.ndjson")
    emitter = EngineEventEmitter(run=run, event_sink=event_sink)

    emitter.console_line("Started run", level="info")
    emitter.phase_start("mapping", file_count=1)
    emitter.table_summary(table)

    events = [json.loads(line) for line in (run.paths.logs_dir / "events.ndjson").read_text().strip().split("\n")]

    assert events[0]["type"] == "console.line"
    assert events[0]["payload"]["message"] == "Started run"
    assert events[1]["type"] == "engine.phase.start"
    assert events[1]["payload"]["phase"] == "mapping"

    table_event = events[2]
    assert table_event["type"] == "engine.table.summary"
    assert table_event["payload"]["row_count"] == 2
    assert table_event["payload"]["validation"]["total"] == 0
    assert table_event["payload"]["mapped_fields"][0]["field"] == "id"
