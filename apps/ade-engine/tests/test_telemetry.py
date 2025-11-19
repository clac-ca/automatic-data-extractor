from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ade_engine.logging import StructuredLogger
from ade_engine.model import JobContext, JobPaths
from ade_engine.telemetry import TelemetryConfig

_PLUGIN_EVENTS: list[tuple[str, dict[str, Any]]] = []


def telemetry_test_sink(job: JobContext, paths: JobPaths):  # pragma: no cover - imported via env
    class _Sink:
        def log(self, event: str, *, job: JobContext, **payload: Any) -> None:
            _PLUGIN_EVENTS.append((event, {"job_id": job.job_id, **payload}))

    return _Sink()


class MemoryArtifact:
    def __init__(self) -> None:
        self.notes: list[tuple[str, dict[str, Any]]] = []

    def start(self, *, job: JobContext, manifest: dict[str, Any]) -> None:  # noqa: D401 - noop
        """Test helper does not persist start payloads."""

    def note(self, message: str, *, level: str = "info", **details: Any) -> None:
        self.notes.append((message, {"level": level, **details}))

    def record_table(self, table: dict[str, Any]) -> None:  # noqa: D401 - noop
        """Test helper does not persist table records."""

    def mark_success(self, *, completed_at, outputs) -> None:  # noqa: D401 - noop
        """Test helper does not persist success payloads."""

    def mark_failure(self, *, completed_at, error) -> None:  # noqa: D401 - noop
        """Test helper does not persist failure payloads."""

    def flush(self) -> None:  # noqa: D401 - noop
        """Test helper does not flush to disk."""


class MemoryEvents:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def log(self, event: str, *, job: JobContext, **payload: Any) -> None:
        self.events.append((event, {"job_id": job.job_id, **payload}))


class StaticProvider:
    def __init__(self, artifact: MemoryArtifact, events: MemoryEvents) -> None:
        self._artifact = artifact
        self._events = events

    def artifact(self, job: JobContext) -> MemoryArtifact:
        return self._artifact

    def events(self, job: JobContext) -> MemoryEvents:
        return self._events


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
    return JobContext(
        job_id="job",
        manifest={},
        paths=paths,
        started_at=datetime.now(timezone.utc),
    )


def test_telemetry_config_controls_levels(tmp_path: Path) -> None:
    job = _job(tmp_path)
    artifact = MemoryArtifact()
    events = MemoryEvents()
    config = TelemetryConfig(
        correlation_id="corr-123",
        min_note_level="info",
        min_event_level="warning",
    )
    telemetry = config.bind(job, job.paths, provider=StaticProvider(artifact, events))
    logger = StructuredLogger(job, telemetry)

    logger.note("debug note", level="debug", detail="suppressed")
    logger.note("info note", level="info", detail="kept")
    logger.event("debug_event", level="debug", flag=True)
    logger.event("warn_event", level="warning", flag=True)

    assert all(message != "debug note" for message, _ in artifact.notes)
    note_details = dict(artifact.notes[0][1])
    assert note_details["level"] == "info"
    assert note_details["correlation_id"] == "corr-123"

    assert all(event != "debug_event" for event, _ in events.events)
    event_name, payload = events.events[0]
    assert event_name == "warn_event"
    assert payload["level"] == "warning"
    assert payload["correlation_id"] == "corr-123"


def test_telemetry_config_broadcasts_to_extra_sinks(tmp_path: Path) -> None:
    job = _job(tmp_path)
    artifact = MemoryArtifact()
    events = MemoryEvents()
    captured: list[tuple[str, dict[str, Any]]] = []

    def extra_factory(job: JobContext, paths: JobPaths):
        class _Sink:
            def log(self, event: str, *, job: JobContext, **payload: Any) -> None:
                captured.append((event, {"job_id": job.job_id, **payload}))

        return _Sink()

    config = TelemetryConfig(event_sink_factories=(extra_factory,))
    telemetry = config.bind(job, job.paths, provider=StaticProvider(artifact, events))
    logger = StructuredLogger(job, telemetry)

    logger.event("broadcast", level="info", flag=True)

    assert captured and captured[0][0] == "broadcast"
    assert captured[0][1]["flag"] is True


def test_telemetry_config_loads_env_sinks(tmp_path: Path, monkeypatch) -> None:
    global _PLUGIN_EVENTS
    _PLUGIN_EVENTS = []
    job = _job(tmp_path)
    artifact = MemoryArtifact()
    events = MemoryEvents()

    monkeypatch.setenv(
        "ADE_TELEMETRY_SINKS",
        "ade_engine.tests.test_telemetry:telemetry_test_sink",
    )

    config = TelemetryConfig()
    telemetry = config.bind(job, job.paths, provider=StaticProvider(artifact, events))
    logger = StructuredLogger(job, telemetry)

    logger.event("env_sink", level="info", extra="value")

    assert _PLUGIN_EVENTS and _PLUGIN_EVENTS[0][0] == "env_sink"
    assert _PLUGIN_EVENTS[0][1]["extra"] == "value"
