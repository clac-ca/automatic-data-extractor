from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from ade_engine.logging import StructuredLogger
from ade_engine.model import JobContext, JobPaths
from ade_engine.pipeline.state import PipelinePhase, PipelineStateMachine, build_result
from ade_engine.telemetry import TelemetryConfig


@dataclass
class DummyArtifact:
    notes: list[tuple[str, dict]] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)

    def note(self, message: str, *, level: str = "info", **details) -> None:
        self.notes.append((message, {"level": level, **details}))

    def record_table(self, table: dict) -> None:
        self.tables.append(table)

    def mark_success(self, **_) -> None:  # pragma: no cover - unused in tests
        pass

    def mark_failure(self, **_) -> None:  # pragma: no cover - unused in tests
        pass

    def flush(self) -> None:
        pass


@dataclass
class DummyEvents:
    events: list[tuple[str, dict]] = field(default_factory=list)

    def log(self, event: str, *, job, **payload) -> None:  # noqa: ANN001 - test helper
        self.events.append((event, {"job_id": job.job_id, **payload}))


@dataclass
class StaticSinkProvider:
    artifact_sink: DummyArtifact
    event_sink: DummyEvents

    def artifact(self, job: JobContext) -> DummyArtifact:  # noqa: D401 - test helper
        """Return the pre-baked artifact sink."""

        return self.artifact_sink

    def events(self, job: JobContext) -> DummyEvents:  # noqa: D401 - test helper
        """Return the pre-baked events sink."""

        return self.event_sink


def _job(tmp_path: Path) -> JobContext:
    paths = JobPaths(
        jobs_root=tmp_path,
        job_dir=tmp_path,
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        logs_dir=tmp_path / "logs",
        artifact_path=tmp_path / "logs" / "artifact.json",
        events_path=tmp_path / "logs" / "events.ndjson",
    )
    return JobContext(job_id="job", manifest={}, paths=paths, started_at=datetime.now(timezone.utc))


def test_pipeline_state_machine_executes_stages(tmp_path: Path) -> None:
    job = _job(tmp_path)
    artifact = DummyArtifact()
    events = DummyEvents()
    telemetry = TelemetryConfig().bind(
        job,
        job.paths,
        provider=StaticSinkProvider(artifact, events),
    )
    logger = StructuredLogger(job, telemetry)
    state = PipelineStateMachine(job, logger)

    extraction = SimpleNamespace(source_name="employees.csv")
    output_file = tmp_path / "output" / "normalized.xlsx"

    state.execute(
        extractor=lambda: [extraction],
        after_extract=lambda tables: None,
        before_save=lambda tables: None,
        writer=lambda tables: output_file,
    )

    assert state.phase is PipelinePhase.COMPLETED
    assert state.output_paths == (output_file,)
    result = build_result(state)
    assert result.status == "succeeded"
    assert result.output_paths == (output_file,)
    assert result.processed_files == ("employees.csv",)
    assert any(event for event, payload in events.events if event == "pipeline_transition")


def test_pipeline_state_machine_blocks_invalid_transition(tmp_path: Path) -> None:
    job = _job(tmp_path)
    telemetry = TelemetryConfig().bind(
        job,
        job.paths,
        provider=StaticSinkProvider(DummyArtifact(), DummyEvents()),
    )
    logger = StructuredLogger(job, telemetry)
    state = PipelineStateMachine(job, logger)

    try:
        state.transition(PipelinePhase.COMPLETED)
    except RuntimeError as exc:
        assert "Invalid pipeline transition" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("transition should have failed")
