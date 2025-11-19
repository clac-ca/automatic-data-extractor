"""Artifact and event sink abstractions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol, runtime_checkable

from ade_schemas import TelemetryEnvelope, TelemetryEvent

from .model import JobContext, JobPaths


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso(moment: datetime | None = None) -> str:
    ts = moment or _now()
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


@runtime_checkable
class ArtifactSink(Protocol):
    """Destination for job artifact data."""

    def start(self, *, job: JobContext, manifest: dict[str, Any]) -> None: ...

    def note(self, message: str, *, level: str = "info", **extra: Any) -> None: ...

    def record_table(self, table: dict[str, Any]) -> None: ...

    def mark_success(self, *, completed_at: datetime, outputs: Iterable[Path]) -> None: ...

    def mark_failure(self, *, completed_at: datetime, error: Exception) -> None: ...

    def flush(self) -> None: ...


@runtime_checkable
class EventSink(Protocol):
    """Structured event consumer."""

    def log(self, event: str, *, job: JobContext, **payload: Any) -> None: ...


@runtime_checkable
class SinkProvider(Protocol):
    """Factory that produces artifact and event sinks for a job."""

    def artifact(self, job: JobContext) -> ArtifactSink: ...

    def events(self, job: JobContext) -> EventSink: ...


EventSinkFactory = Callable[[JobContext, JobPaths], EventSink]


class FileArtifactSink:
    """Persist job artifact JSON with atomic writes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {}

    def start(self, *, job: JobContext, manifest: dict[str, Any]) -> None:
        self.data = {
            "schema": "ade.artifact/v1alpha",
            "artifact_version": "0.1.0",
            "job": {
                "job_id": job.job_id,
                "status": "running",
                "started_at": _now_iso(job.started_at),
            },
            "config": {
                "schema": manifest.get("info", {}).get("schema"),
                "manifest_version": manifest.get("info", {}).get("version"),
            },
            "tables": [],
            "notes": [],
        }
        self.flush()

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(self.path)

    def note(self, message: str, *, level: str = "info", **extra: Any) -> None:
        entry = {"timestamp": _now_iso(), "level": level, "message": message}
        if extra:
            entry["details"] = extra
        self.data.setdefault("notes", []).append(entry)

    def record_table(self, table: dict[str, Any]) -> None:
        self.data.setdefault("tables", []).append(table)

    def mark_success(self, *, completed_at: datetime, outputs: Iterable[Path]) -> None:
        self.data["job"].update(
            {
                "status": "succeeded",
                "completed_at": _now_iso(completed_at),
                "outputs": [str(path) for path in outputs],
            }
        )

    def mark_failure(self, *, completed_at: datetime, error: Exception) -> None:
        self.data["job"].update(
            {
                "status": "failed",
                "completed_at": _now_iso(completed_at),
                "error": {
                    "type": error.__class__.__name__,
                    "message": str(error),
                },
            }
        )


class FileEventSink:
    """Append structured job lifecycle events to ``events.ndjson``."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def log(self, event: str, *, job: JobContext, **payload: Any) -> None:
        payload_data = dict(payload)
        level = str(payload_data.pop("level", "info"))
        event_payload = TelemetryEvent(name=event, level=level, **payload_data)
        envelope = TelemetryEnvelope(
            job_id=job.job_id,
            run_id=str(job.metadata.get("run_id")) if job.metadata.get("run_id") else None,
            emitted_at=_now(),
            event=event_payload,
        )
        serialized = envelope.model_dump_json()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(serialized + "\n")


class DispatchEventSink:
    """Broadcast telemetry events to multiple sinks."""

    def __init__(self, sinks: Iterable[EventSink]) -> None:
        self._sinks = tuple(sinks)

    def log(self, event: str, *, job: JobContext, **payload: Any) -> None:
        for sink in self._sinks:
            sink.log(event, job=job, **payload)


class FileSinkProvider:
    """Provide file-backed sinks for a job."""

    def __init__(self, paths: JobPaths) -> None:
        self._paths = paths

    def artifact(self, job: JobContext) -> ArtifactSink:
        return FileArtifactSink(self._paths.artifact_path)

    def events(self, job: JobContext) -> EventSink:
        return FileEventSink(self._paths.events_path)


__all__ = [
    "ArtifactSink",
    "EventSink",
    "EventSinkFactory",
    "FileArtifactSink",
    "FileEventSink",
    "DispatchEventSink",
    "FileSinkProvider",
    "SinkProvider",
    "_now",
    "_now_iso",
]
