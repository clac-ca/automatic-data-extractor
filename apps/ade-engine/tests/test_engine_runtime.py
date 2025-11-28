from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import load_workbook

from ade_engine import Engine, RunRequest, RunStatus, run
from ade_engine.schemas.telemetry import AdeEvent
from fixtures.config_factories import clear_config_import, make_minimal_config
from fixtures.sample_inputs import (
    sample_csv,
    sample_large_csv,
    sample_xlsx_multi_sheet,
    sample_xlsx_single_sheet,
)


@pytest.fixture(autouse=True)
def _cleanup_imports() -> None:
    yield
    clear_config_import()


def _parse_events(path: Path) -> list[AdeEvent]:
    return [AdeEvent.model_validate_json(line) for line in path.read_text().splitlines() if line]


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

    events_path = Path(result.logs_dir) / "events.ndjson"
    events = _parse_events(events_path)

    assert any(evt.type == "run.completed" and evt.model_extra.get("status") == "succeeded" for evt in events)
    table_event = next(evt for evt in events if evt.type == "run.table.summary")
    table = table_event.model_extra
    assert table["row_count"] == 2


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
    events_path = Path(result.logs_dir) / "events.ndjson"
    events = _parse_events(events_path)
    completion = next(evt for evt in events if evt.type == "run.completed")
    assert completion.model_extra.get("status") == "failed"


def test_engine_mapping_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = make_minimal_config(tmp_path, monkeypatch, include_transform=False, include_validator=False)
    source = sample_xlsx_multi_sheet(tmp_path)

    result = run(
        manifest_path=config.manifest_path,
        input_files=[source],
        output_dir=tmp_path / "out",
        logs_dir=tmp_path / "logs",
    )

    events_path = Path(result.logs_dir) / "events.ndjson"
    events = _parse_events(events_path)
    table_event = next(evt for evt in events if evt.type == "run.table.summary")
    table = table_event.model_extra

    mapped_fields = [
        {key: field.get(key) for key in ("field", "header", "score", "source_column_index")}
        for field in table.get("mapped_fields", [])
    ]
    unmapped_columns = table.get("unmapped_columns") or []

    assert mapped_fields == [
        {"field": "member_id", "header": "member_id", "score": 1.0, "source_column_index": 0},
        {"field": "value", "header": "value", "score": 1.0, "source_column_index": 1},
    ]
    assert unmapped_columns == [
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
