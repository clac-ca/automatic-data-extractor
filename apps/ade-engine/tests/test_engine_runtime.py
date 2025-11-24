from __future__ import annotations

import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from ade_engine import Engine, RunRequest, RunStatus, run
from ade_engine.schemas.artifact import ArtifactV1
from ade_engine.schemas.telemetry import TelemetryEnvelope
from tests.fixtures.config_factories import clear_config_import, make_minimal_config
from tests.fixtures.sample_inputs import sample_csv, sample_large_csv, sample_xlsx_multi_sheet, sample_xlsx_single_sheet


@pytest.fixture(autouse=True)
def _cleanup_imports() -> None:
    yield
    clear_config_import()


def _parse_events(path: Path) -> list[TelemetryEnvelope]:
    return [TelemetryEnvelope.model_validate_json(line) for line in path.read_text().splitlines() if line]


def test_engine_run_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = make_minimal_config(tmp_path, monkeypatch, include_transform=True, include_validator=True)
    source = sample_xlsx_single_sheet(tmp_path)

    result = run(
        manifest_path=config.manifest_path,
        input_files=[source],
        output_dir=tmp_path / "out",
        logs_dir=tmp_path / "logs",
        metadata={"test_case": "end_to_end"},
    )

    assert result.status is RunStatus.SUCCEEDED
    workbook_path = Path(result.output_paths[0])
    assert workbook_path.exists()

    workbook = load_workbook(workbook_path)
    try:
        sheet = workbook["Normalized"]
        assert [cell.value for cell in next(sheet.iter_rows(min_row=1, max_row=1))] == ["member_id", "value", "raw_3"]
    finally:
        workbook.close()

    artifact = ArtifactV1.model_validate_json(Path(result.artifact_path).read_text())
    assert artifact.run.status == "succeeded"
    assert artifact.tables

    events = _parse_events(Path(result.events_path))
    names = [env.event.event for env in events]
    assert "run_started" in names and "run_completed" in names


def test_engine_run_hook_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = make_minimal_config(tmp_path, monkeypatch, include_hooks=True, failing_hook=True)
    source = sample_csv(tmp_path)

    request = RunRequest(
        manifest_path=config.manifest_path,
        input_files=[source],
        output_dir=tmp_path / "out",
        logs_dir=tmp_path / "logs",
    )
    result = Engine().run(request)

    assert result.status is RunStatus.FAILED
    assert result.error is not None
    artifact = json.loads(Path(result.artifact_path).read_text())
    assert artifact["run"]["status"] == "failed"


def test_engine_mapping_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = make_minimal_config(tmp_path, monkeypatch, include_transform=False, include_validator=False)
    source = sample_xlsx_multi_sheet(tmp_path)

    result = run(
        manifest_path=config.manifest_path,
        input_files=[source],
        output_dir=tmp_path / "out",
        logs_dir=tmp_path / "logs",
    )

    artifact = ArtifactV1.model_validate_json(Path(result.artifact_path).read_text())
    table = artifact.tables[0]

    mapping_snapshot = [
        {"field": col.field, "header": col.header, "score": col.score, "source_column_index": col.source_column_index}
        for col in table.mapped_columns
    ]
    unmapped_snapshot = [
        {
            "header": col.header,
            "source_column_index": col.source_column_index,
            "output_header": col.output_header,
        }
        for col in table.unmapped_columns
    ]

    assert mapping_snapshot == [
        {"field": "member_id", "header": "member_id", "score": 1.0, "source_column_index": 0},
        {"field": "value", "header": "value", "score": 1.0, "source_column_index": 1},
    ]
    assert unmapped_snapshot == [
        {"header": "note", "source_column_index": 2, "output_header": "raw_3"},
        {"header": "surplus", "source_column_index": 3, "output_header": "raw_4"},
    ]


def test_engine_large_input_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = make_minimal_config(tmp_path, monkeypatch)
    source = sample_large_csv(tmp_path, rows=2000)

    result = run(
        manifest_path=config.manifest_path,
        input_files=[source],
        output_dir=tmp_path / "out",
        logs_dir=tmp_path / "logs",
    )

    assert result.status is RunStatus.SUCCEEDED
    assert Path(result.output_paths[0]).exists()
