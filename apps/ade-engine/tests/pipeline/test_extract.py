from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import openpyxl
import pytest

from ade_engine.config.loader import load_config_runtime
from ade_engine.core.pipeline import extract_raw_tables
from ade_engine.core.types import RunContext, RunPaths, RunRequest
from ade_engine.core.errors import InputError


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


def _write_manifest(pkg_dir: Path) -> Path:
    manifest = {
        "schema": "ade.manifest/v1",
        "version": "1.0.0",
        "script_api_version": 1,
        "columns": {"order": [], "fields": {}},
        "hooks": {
            "on_run_start": [],
            "on_after_extract": [],
            "on_after_mapping": [],
            "on_before_save": [],
            "on_run_end": [],
        },
        "writer": {"append_unmapped_columns": False, "unmapped_prefix": "raw_", "output_sheet": "Normalized"},
    }
    manifest_path = pkg_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


def _write_row_detector(pkg_dir: Path) -> None:
    detector_dir = pkg_dir / "row_detectors"
    detector_dir.mkdir()
    (detector_dir / "__init__.py").write_text("")
    (detector_dir / "simple.py").write_text(
        """
def detect_labels(*, row_values, **_):
    cells = [str(c or "").lower() for c in row_values]
    header_score = 1.0 if cells and cells[0].startswith("header") else 0.0
    data_score = 1.0 if any(cells) and not header_score else 0.0
    return {"scores": {"header": header_score, "data": data_score}}
"""
    )


def _make_run_context(tmp_path: Path, run_request: RunRequest, manifest: object) -> RunContext:
    paths = RunPaths(
        input_dir=run_request.input_dir or tmp_path,
        output_dir=tmp_path / "out",
        logs_dir=tmp_path / "logs",
        artifact_path=tmp_path / "artifact.json",
        events_path=tmp_path / "events.ndjson",
    )
    return RunContext(
        run_id="run-1",
        metadata={},
        manifest=manifest,
        paths=paths,
        started_at=datetime.utcnow(),
    )


def test_detects_single_table_from_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)
    manifest_path = _write_manifest(pkg_dir)
    _write_row_detector(pkg_dir)

    source_file = tmp_path / "input.csv"
    source_file.write_text("Header A,Header B\nvalue-1,1\nvalue-2,2\n")

    runtime = load_config_runtime(manifest_path=manifest_path)
    request = RunRequest(input_files=[source_file])
    run = _make_run_context(tmp_path, request, runtime.manifest)

    tables = extract_raw_tables(request=request, run=run, runtime=runtime)

    assert len(tables) == 1
    table = tables[0]
    assert table.table_index == 0
    assert table.source_sheet is None
    assert table.header_row == ["Header A", "Header B"]
    assert table.header_row_index == 1
    assert table.first_data_row_index == 2
    assert table.last_data_row_index == 3
    assert table.data_rows == [["value-1", "1"], ["value-2", "2"]]


def test_detects_multiple_tables_per_sheet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)
    manifest_path = _write_manifest(pkg_dir)
    _write_row_detector(pkg_dir)

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    sheet.append(["Header One", "Value"])
    sheet.append(["row-a", 1])
    sheet.append(["row-b", 2])
    sheet.append([None, None])
    sheet.append(["Header Two", "Value"])
    sheet.append(["row-c", 3])
    source_file = tmp_path / "input.xlsx"
    workbook.save(source_file)

    runtime = load_config_runtime(manifest_path=manifest_path)
    request = RunRequest(input_files=[source_file])
    run = _make_run_context(tmp_path, request, runtime.manifest)

    tables = extract_raw_tables(request=request, run=run, runtime=runtime)

    assert [(t.table_index, t.source_sheet) for t in tables] == [(0, "Data"), (1, "Data")]
    assert tables[0].header_row_index == 1
    assert tables[0].first_data_row_index == 2
    assert tables[0].last_data_row_index == 3
    assert tables[1].header_row_index == 5
    assert tables[1].first_data_row_index == 6
    assert tables[1].last_data_row_index == 6


def test_missing_requested_sheet_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)
    manifest_path = _write_manifest(pkg_dir)
    _write_row_detector(pkg_dir)

    workbook = openpyxl.Workbook()
    workbook.save(tmp_path / "input.xlsx")

    runtime = load_config_runtime(manifest_path=manifest_path)
    request = RunRequest(input_files=[tmp_path / "input.xlsx"], input_sheets=["Missing"])
    run = _make_run_context(tmp_path, request, runtime.manifest)

    with pytest.raises(InputError) as excinfo:
        extract_raw_tables(request=request, run=run, runtime=runtime)

    assert "Worksheet(s) Missing not found" in str(excinfo.value)
