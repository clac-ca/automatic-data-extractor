from __future__ import annotations

from pathlib import Path

from ade_api.features.runs.summary_builder import (
    build_run_summary,
    build_run_summary_from_paths,
)
from ade_engine.schemas import AdeEvent, ArtifactV1, ManifestV1


FIXTURES = Path(__file__).parent / "fixtures"


def _load_events(path: Path) -> list[AdeEvent]:
    return [
        AdeEvent.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_build_run_summary_happy_path():
    artifact = ArtifactV1.model_validate_json(
        (FIXTURES / "artifact_success.json").read_text(encoding="utf-8")
    )
    events = _load_events(FIXTURES / "events_success.ndjson")
    manifest = ManifestV1.model_validate_json(
        (FIXTURES / "manifest.json").read_text(encoding="utf-8")
    )

    summary = build_run_summary(
        artifact=artifact,
        events=events,
        manifest=manifest,
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


def test_build_run_summary_missing_events_sets_row_counts_none():
    artifact = ArtifactV1.model_validate_json(
        (FIXTURES / "artifact_success.json").read_text(encoding="utf-8")
    )
    manifest = ManifestV1.model_validate_json(
        (FIXTURES / "manifest.json").read_text(encoding="utf-8")
    )

    summary = build_run_summary(
        artifact=artifact,
        events=[],
        manifest=manifest,
        workspace_id="ws_1",
        configuration_id="cfg_1",
        configuration_version="1.2.3",
        run_id="run_1",
    )

    assert summary.core.row_count is None
    assert summary.breakdowns.by_file[0].row_count is None


def test_build_run_summary_handles_failures():
    artifact = ArtifactV1.model_validate_json(
        (FIXTURES / "artifact_failure.json").read_text(encoding="utf-8")
    )
    events = _load_events(FIXTURES / "events_failure.ndjson")
    manifest = ManifestV1.model_validate_json(
        (FIXTURES / "manifest.json").read_text(encoding="utf-8")
    )

    summary = build_run_summary(
        artifact=artifact,
        events=events,
        manifest=manifest,
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
    artifact_path = tmp_path / "artifact.json"
    events_path = tmp_path / "events.ndjson"
    manifest_path = tmp_path / "manifest.json"

    artifact_path.write_text(
        (FIXTURES / "artifact_success.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    events_path.write_text(
        (FIXTURES / "events_success.ndjson").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    manifest_path.write_text(
        (FIXTURES / "manifest.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    summary = build_run_summary_from_paths(
        artifact_path=artifact_path,
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
