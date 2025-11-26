from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ade_api.features.runs.summary_builder import build_run_summary, build_run_summary_from_paths
from ade_engine.schemas import AdeEvent, ManifestV1


FIXTURES = Path(__file__).parent / "fixtures"


def _dt(seconds: int) -> datetime:
    return datetime(2024, 1, 1, 0, 0, seconds, tzinfo=timezone.utc)


def _manifest() -> ManifestV1:
    return ManifestV1.model_validate_json((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


def _success_events(run_id: str = "run_1") -> list[AdeEvent]:
    return [
        AdeEvent(
            type="run.started",
            created_at=_dt(0),
            run_id=run_id,
            run={"status": "running", "engine_version": "0.2.0"},
        ),
        AdeEvent(
            type="run.table.summary",
            created_at=_dt(1),
            run_id=run_id,
            output_delta={
                "kind": "table_summary",
                "table": {
                    "source_file": "input.xlsx",
                    "source_sheet": "Sheet1",
                    "table_index": 0,
                    "row_count": 10,
                    "mapped_fields": [
                        {"field": "member_id", "score": 1.0, "is_required": True, "is_satisfied": True},
                        {"field": "email", "score": 0.82, "is_required": True, "is_satisfied": False},
                    ],
                    "unmapped_column_count": 1,
                    "validation": {
                        "total": 3,
                        "by_severity": {"error": 2, "warning": 1},
                        "by_code": {"missing": 1, "invalid": 1, "empty": 1},
                        "by_field": {
                            "email": {
                                "total": 2,
                                "by_severity": {"error": 2},
                                "by_code": {"missing": 1, "invalid": 1},
                            },
                            "member_id": {
                                "total": 1,
                                "by_severity": {"warning": 1},
                                "by_code": {"empty": 1},
                            },
                        },
                    },
                },
            },
        ),
        AdeEvent(
            type="run.table.summary",
            created_at=_dt(2),
            run_id=run_id,
            output_delta={
                "kind": "table_summary",
                "table": {
                    "source_file": "input.xlsx",
                    "source_sheet": "Sheet1",
                    "table_index": 1,
                    "row_count": 5,
                    "mapped_fields": [
                        {"field": "member_id", "score": 0.91, "is_required": True, "is_satisfied": True},
                    ],
                    "unmapped_column_count": 0,
                    "validation": {"total": 0, "by_severity": {}, "by_code": {}, "by_field": {}},
                },
            },
        ),
        AdeEvent(
            type="run.completed",
            created_at=_dt(3),
            run_id=run_id,
            run={"status": "succeeded"},
        ),
    ]


def _failure_events(run_id: str = "run_2") -> list[AdeEvent]:
    return [
        AdeEvent(
            type="run.started",
            created_at=_dt(0),
            run_id=run_id,
            run={"status": "running", "engine_version": "0.2.0"},
        ),
        AdeEvent(
            type="run.completed",
            created_at=_dt(1),
            run_id=run_id,
            run={"status": "failed", "error": {"code": "pipeline_error", "message": "boom"}},
        ),
    ]


def test_build_run_summary_happy_path():
    summary = build_run_summary(
        events=_success_events(),
        manifest=_manifest(),
        workspace_id="ws_1",
        configuration_id="cfg_1",
        configuration_version="1.2.3",
        run_id="run_1",
    )

    assert summary.run.status == "succeeded"
    assert summary.run.engine_version == "0.2.0"
    assert summary.core.table_count == 2
    assert summary.core.row_count == 15
    assert summary.core.unmapped_column_count == 1
    assert summary.core.validation_issue_count_total == 3
    assert summary.core.issue_counts_by_severity == {"error": 2, "warning": 1}
    assert summary.breakdowns.by_file[0].row_count == 15

    email = next(item for item in summary.breakdowns.by_field if item.field == "email")
    assert email.validation_issue_count_total == 2
    assert email.mapped is True
    assert abs(email.max_score - 0.82) < 1e-9


def test_build_run_summary_missing_row_counts_sets_none():
    events = _success_events()
    events[1].output_delta["table"].pop("row_count", None)  # type: ignore[index]

    summary = build_run_summary(
        events=events,
        manifest=_manifest(),
        workspace_id="ws_1",
        configuration_id="cfg_1",
        configuration_version="1.2.3",
        run_id="run_1",
    )

    assert summary.core.row_count is None
    assert summary.breakdowns.by_file[0].row_count is None


def test_build_run_summary_handles_failures():
    summary = build_run_summary(
        events=_failure_events(),
        manifest=_manifest(),
        workspace_id="ws_1",
        configuration_id="cfg_1",
        configuration_version="1.2.3",
        run_id="run_2",
    )

    assert summary.run.status == "failed"
    assert summary.run.failure_code == "pipeline_error"
    assert summary.core.table_count == 0
    assert summary.core.validation_issue_count_total == 0


def test_build_run_summary_from_paths_reads_files(tmp_path: Path):
    events_path = tmp_path / "events.ndjson"
    manifest_path = tmp_path / "manifest.json"

    events_payload = "\n".join(event.model_dump_json() for event in _success_events("external_run_id"))
    events_path.write_text(events_payload, encoding="utf-8")
    manifest_path.write_text(
        (FIXTURES / "manifest.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    summary = build_run_summary_from_paths(
        events_path=events_path,
        manifest_path=manifest_path,
        workspace_id="ws_1",
        configuration_id="cfg_1",
        configuration_version="1.2.3",
        run_id="external_run_id",
    )

    assert summary.run.id == "external_run_id"
    assert summary.core.table_count == 2
    assert summary.core.row_count == 15
