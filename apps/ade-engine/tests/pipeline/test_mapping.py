import json
from datetime import datetime
from pathlib import Path
import sys

import pytest

from ade_engine.config.loader import load_config_runtime
from ade_engine.core.pipeline import map_extracted_tables
from ade_engine.core.types import ExtractedTable, RunContext, RunPaths, RunRequest


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


def _write_manifest(pkg_dir: Path, *, order: list[str]) -> Path:
    manifest = {
        "schema": "ade.manifest/v1",
        "version": "1.0.0",
        "script_api_version": 2,
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
        "writer": {"append_unmapped_columns": True, "unmapped_prefix": "raw_", "output_sheet": "Normalized"},
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
        input_dir=request.input_dir or tmp_path,
        output_dir=tmp_path / "out",
        logs_dir=tmp_path / "logs",
    )
    return RunContext(
        run_id="run-1",
        metadata={},
        manifest=manifest,
        paths=paths,
        started_at=datetime.utcnow(),
    )


def test_maps_columns_to_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)
    manifest_path = _write_manifest(pkg_dir, order=["alpha", "beta"])
    _write_column_detector(
        pkg_dir,
        "alpha",
        """
def detect_header(*, header, **_):
    return 1.0 if header.lower() == "alpha" else 0.0
""",
    )
    _write_column_detector(
        pkg_dir,
        "beta",
        """
def detect_header(*, header, **_):
    return 1.0 if header.lower() == "beta" else 0.0
""",
    )

    runtime = load_config_runtime(manifest_path=manifest_path)
    request = RunRequest(input_dir=tmp_path)
    run = _run_context(tmp_path, runtime.manifest, request)

    raw = ExtractedTable(
        source_file=tmp_path / "input.csv",
        source_sheet=None,
        table_index=0,
        header_row=["Alpha", "Beta"],
        data_rows=[["a1", "b1"], ["a2", "b2"]],
        header_row_index=1,
        first_data_row_index=2,
        last_data_row_index=3,
    )

    mapped = map_extracted_tables(tables=[raw], runtime=runtime, run=run)[0]
    assert [mc.field for mc in mapped.column_map.mapped_columns] == ["alpha", "beta"]
    assert [mc.source_column_index for mc in mapped.column_map.mapped_columns] == [0, 1]
    assert all(mc.is_satisfied for mc in mapped.column_map.mapped_columns)


def test_tie_breaks_by_manifest_order_and_column_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)
    manifest_path = _write_manifest(pkg_dir, order=["first", "second"])
    detector_body = """
def detect_equal(*, header, **_):
    return 0.6
"""
    _write_column_detector(pkg_dir, "first", detector_body)
    _write_column_detector(pkg_dir, "second", detector_body)

    runtime = load_config_runtime(manifest_path=manifest_path)
    request = RunRequest(input_dir=tmp_path)
    run = _run_context(tmp_path, runtime.manifest, request)

    raw = ExtractedTable(
        source_file=tmp_path / "input.csv",
        source_sheet=None,
        table_index=0,
        header_row=["Col1", "Col2"],
        data_rows=[["v1", "v2"]],
        header_row_index=1,
        first_data_row_index=2,
        last_data_row_index=2,
    )

    mapped = map_extracted_tables(tables=[raw], runtime=runtime, run=run)[0]
    chosen_columns = {mc.field: mc.source_column_index for mc in mapped.column_map.mapped_columns if mc.is_satisfied}
    assert chosen_columns == {"first": 0, "second": 1}


def test_below_threshold_field_marks_unmapped_and_preserves_unmapped_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pkg_dir = _bootstrap_package(tmp_path, monkeypatch)
    manifest_path = _write_manifest(pkg_dir, order=["only_field"])
    _write_column_detector(
        pkg_dir,
        "only_field",
        """
def detect_low(*, header, **_):
    return 0.2
""",
    )

    runtime = load_config_runtime(manifest_path=manifest_path)
    request = RunRequest(input_dir=tmp_path)
    run = _run_context(tmp_path, runtime.manifest, request)

    raw = ExtractedTable(
        source_file=tmp_path / "input.csv",
        source_sheet=None,
        table_index=0,
        header_row=["Noise"],
        data_rows=[["v1"], ["v2"]],
        header_row_index=1,
        first_data_row_index=2,
        last_data_row_index=3,
    )

    mapped = map_extracted_tables(tables=[raw], runtime=runtime, run=run)[0]
    field_mapping = mapped.column_map.mapped_columns[0]
    assert field_mapping.field == "only_field"
    assert field_mapping.is_satisfied is False
    assert mapped.column_map.unmapped_columns[0].output_header == "raw_1"
