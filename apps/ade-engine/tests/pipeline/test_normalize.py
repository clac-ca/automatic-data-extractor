import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from ade_engine.config.loader import load_config_runtime
from ade_engine.core.pipeline import map_extracted_tables, normalize_table
from ade_engine.core.types import ExtractedTable, RunContext, RunPaths, RunRequest
from ade_engine.infra.event_emitter import ConfigEventEmitter, EngineEventEmitter
from ade_engine.infra.telemetry import FileEventSink


def _clear_import_cache(prefix: str = "ade_config") -> None:
    for name in list(sys.modules):
        if name == prefix or name.startswith(f"{prefix}."):
            sys.modules.pop(name)


def _bootstrap_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pkg_dir = tmp_path / "ade_config"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    _clear_import_cache()
    return pkg_dir


def _write_manifest(pkg_dir: Path, *, order: list[str], append_unmapped: bool = True) -> Path:
    manifest = {
        "schema": "ade.manifest/v1",
        "version": "1.0.0",
        "script_api_version": 3,
        "columns": {
            "order": order,
            "fields": {field: {"label": field, "module": f"column_detectors.{field}", "required": False} for field in order},
        },
        "hooks": {
            "on_run_start": [],
            "on_after_extract": [],
            "on_after_mapping": [],
            "on_before_save": [],
            "on_run_end": [],
        },
        "writer": {
            "append_unmapped_columns": append_unmapped,
            "unmapped_prefix": "raw_",
        },
    }
    manifest_path = pkg_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


def _write_column_detector(pkg_dir: Path, field: str, body: str) -> None:
    detector_dir = pkg_dir / "column_detectors"
    detector_dir.mkdir(exist_ok=True)
    (detector_dir / "__init__.py").write_text("")
    (detector_dir / f"{field}.py").write_text(body)


def _run_context(tmp_path: Path, manifest: object, request: RunRequest) -> RunContext:
    paths = RunPaths(
        input_file=request.input_file or tmp_path / "input.csv",
        output_dir=tmp_path / "out",
        logs_dir=tmp_path / "logs",
    )
    return RunContext(
        run_id=uuid4(),
        metadata={},
        manifest=manifest,
        paths=paths,
        started_at=datetime.utcnow(),
    )


def _event_emitters(run: RunContext) -> tuple[EngineEventEmitter, ConfigEventEmitter]:
    sink = FileEventSink(path=run.paths.logs_dir / "events.ndjson")
    engine_emitter = EngineEventEmitter(run=run, event_sink=sink)
    return engine_emitter, engine_emitter.config_emitter()


class _DummyLogger:
    def __getattr__(self, name: str):  # pragma: no cover - logging noop
        def _noop(*_: object, **__: object) -> None:
            return None

        return _noop


def test_transform_applied_and_rows_preserve_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)
    manifest_path = _write_manifest(pkg_dir, order=["name", "age"])
    _write_column_detector(
        pkg_dir,
        "name",
        """
def detect_header(*, header, logger, event_emitter, **_):
    return 1.0 if header.lower() == "name" else 0.0

def transform(*, value, row, logger, event_emitter, **_):
    row["name"] = value.upper()
""",
    )
    _write_column_detector(
        pkg_dir,
        "age",
        """
def detect_header(*, header, logger, event_emitter, **_):
    return 1.0 if header.lower() == "age" else 0.0

def transform(*, value, logger, event_emitter, **_):
    return {"age": value + 1}
""",
    )

    runtime = load_config_runtime(manifest_path=manifest_path)
    request = RunRequest(input_file=tmp_path / "input.csv")
    run = _run_context(tmp_path, runtime.manifest, request)
    engine_emitter, config_emitter = _event_emitters(run)

    raw = ExtractedTable(
        source_file=tmp_path / "input.csv",
        source_sheet=None,
        table_index=0,
        header_row=["Name", "Age", "Note"],
        data_rows=[["alice", 30, "x"], ["bob", 40, "y"]],
        header_row_index=1,
        first_data_row_index=2,
        last_data_row_index=3,
    )

    mapped = map_extracted_tables(
        tables=[raw],
        runtime=runtime,
        run=run,
        event_emitter=engine_emitter,
        config_event_emitter=config_emitter,
    )[0]
    normalized = normalize_table(
        ctx=run,
        cfg=runtime,
        mapped=mapped,
        logger=_DummyLogger(),
        event_emitter=engine_emitter,
        config_event_emitter=config_emitter,
    )

    assert normalized.rows == [["ALICE", 31, "x"], ["BOB", 41, "y"]]
    assert normalized.validation_issues == []
    assert normalized.output_sheet_name == ""


def test_validator_collects_issues_with_row_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)
    manifest_path = _write_manifest(pkg_dir, order=["email"])
    _write_column_detector(
        pkg_dir,
        "email",
        """
def detect_header(*, header, logger, event_emitter, **_):
    return 1.0 if header.lower() == "email" else 0.0

def validate(*, value, row_index, logger, event_emitter, **_):
    if "@" not in value:
        return [
            {"code": "invalid_email", "severity": "error", "message": "missing @"},
            {"code": "short_email", "severity": "warning", "message": f"row {row_index}"},
        ]
    return []
""",
    )

    runtime = load_config_runtime(manifest_path=manifest_path)
    request = RunRequest(input_file=tmp_path / "input.csv")
    run = _run_context(tmp_path, runtime.manifest, request)
    engine_emitter, config_emitter = _event_emitters(run)

    raw = ExtractedTable(
        source_file=tmp_path / "input.csv",
        source_sheet=None,
        table_index=0,
        header_row=["Email"],
        data_rows=[["invalid"], ["valid@example.com"]],
        header_row_index=5,
        first_data_row_index=6,
        last_data_row_index=7,
    )

    mapped = map_extracted_tables(
        tables=[raw],
        runtime=runtime,
        run=run,
        event_emitter=engine_emitter,
        config_event_emitter=config_emitter,
    )[0]
    normalized = normalize_table(
        ctx=run,
        cfg=runtime,
        mapped=mapped,
        logger=_DummyLogger(),
        event_emitter=engine_emitter,
        config_event_emitter=config_emitter,
    )

    assert normalized.rows[0][0] == "invalid"
    assert normalized.rows[1][0] == "valid@example.com"

    assert [i.code for i in normalized.validation_issues] == ["invalid_email", "short_email"]
    assert all(issue.field == "email" for issue in normalized.validation_issues)
    assert {issue.row_index for issue in normalized.validation_issues} == {6}


def test_normalizes_empty_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)
    manifest_path = _write_manifest(pkg_dir, order=["field"], append_unmapped=False)
    _write_column_detector(
        pkg_dir,
        "field",
        """
def detect_header(*, header, logger, event_emitter, **_):
    return 1.0 if header.lower() == "field" else 0.0
""",
    )

    runtime = load_config_runtime(manifest_path=manifest_path)
    request = RunRequest(input_file=tmp_path / "input.csv")
    run = _run_context(tmp_path, runtime.manifest, request)
    engine_emitter, config_emitter = _event_emitters(run)

    raw = ExtractedTable(
        source_file=tmp_path / "input.csv",
        source_sheet=None,
        table_index=0,
        header_row=["Field"],
        data_rows=[],
        header_row_index=1,
        first_data_row_index=2,
        last_data_row_index=1,
    )

    mapped = map_extracted_tables(
        tables=[raw],
        runtime=runtime,
        run=run,
        event_emitter=engine_emitter,
        config_event_emitter=config_emitter,
    )[0]
    normalized = normalize_table(
        ctx=run,
        cfg=runtime,
        mapped=mapped,
        logger=_DummyLogger(),
        event_emitter=engine_emitter,
        config_event_emitter=config_emitter,
    )

    assert normalized.rows == []
    assert normalized.validation_issues == []
