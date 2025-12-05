from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ade_engine.core.types import RunContext
from ade_engine.schemas import (
    FileSummary,
    RunCompletedPayload,
    RunSummary,
    SheetSummary,
    TableSummary,
)

from .telemetry import EventSink, _aggregate_validation, _make_event


@dataclass
class _SequenceCounter:
    """Monotonic counter shared across emitters for a single run."""

    value: int = 0

    def next(self) -> int:
        self.value += 1
        return self.value


class BaseNdjsonEmitter:
    """Lightweight NDJSON emitter that writes AdeEvent objects to sinks."""

    def __init__(
        self,
        *,
        run: RunContext,
        event_sink: EventSink | None = None,
        source: str = "engine",
        sequence: _SequenceCounter | None = None,
    ) -> None:
        self.run = run
        self.event_sink = event_sink
        self.source = source
        self._sequence = sequence or _SequenceCounter()
        self._run_root = self._resolve_run_root()

    def _resolve_run_root(self) -> Path | None:
        try:
            paths = getattr(self.run, "paths", None)
            candidates = [
                getattr(paths, "logs_dir", None) if paths else None,
                getattr(paths, "output_dir", None) if paths else None,
            ]
            for candidate in candidates:
                if candidate:
                    try:
                        return Path(candidate).absolute().parent
                    except Exception:
                        continue
        except Exception:
            return None
        return None

    def _relativize(self, value: Any) -> str | Any:
        if value is None:
            return None
        if self._run_root is None:
            return str(value)
        try:
            path = Path(value)
        except Exception:
            return str(value)

        try:
            if path.is_absolute():
                return str(path.relative_to(self._run_root))
            return str(path)
        except Exception:
            return str(value)

    def _normalize_payload(self, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        if payload is None:
            return None

        def normalize(obj: Any) -> Any:
            if isinstance(obj, dict):
                normalized: dict[str, Any] = {}
                for key, value in obj.items():
                    if value is None:
                        continue
                    if key in {"output_path", "processed_file", "events_path", "source_file", "file_path"}:
                        normalized[key] = self._relativize(value)
                        continue
                    if isinstance(value, dict) or isinstance(value, list):
                        nested = normalize(value)
                        if nested not in (None, {}, []):
                            normalized[key] = nested
                        continue
                    normalized[key] = value
                return normalized
            if isinstance(obj, list):
                return [item for item in (normalize(item) for item in obj) if item not in (None, {}, [])]
            return obj

        return normalize(payload)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _emit(self, type_: str, *, payload: dict[str, Any] | None = None):
        if not self.event_sink:
            return None

        normalized_payload = self._normalize_payload(payload) if isinstance(payload, dict) else payload
        event = _make_event(
            run=self.run,
            type_=type_,
            payload=normalized_payload or None,
            sequence=self._sequence.next(),
            source=self.source,
        )
        self.event_sink.emit(event)
        return event

    # ------------------------------------------------------------------ #
    # Public helpers
    # ------------------------------------------------------------------ #

    def console_line(
        self,
        message: str,
        *,
        level: str = "info",
        stream: str = "stdout",
        scope: str = "run",
        logger: str | None = None,
        engine_timestamp: int | float | str | None = None,
        **details: Any,
    ):
        """Emit a standardized console.line event (used internally for log bridging)."""

        payload: dict[str, Any] = {
            "scope": scope,
            "message": message,
            "level": level,
            "stream": stream,
        }
        if logger:
            payload["logger"] = logger
        if engine_timestamp is not None:
            payload["engine_timestamp"] = engine_timestamp
        if details:
            payload["details"] = details
        return self._emit("console.line", payload=payload)


class EngineEventEmitter(BaseNdjsonEmitter):
    """Run-scoped emitter for engine-owned telemetry (engine.*)."""

    prefix = "engine"

    # ------------------------------------------------------------------ #
    # Engine event helpers
    # ------------------------------------------------------------------ #

    def custom(self, type_suffix: str, **payload: Any):
        return self._emit(f"{self.prefix}.{type_suffix}", payload=payload or None)

    def start(
        self,
        *,
        engine_version: str | None = None,
        config_version: str | None = None,
        env: dict[str, Any] | None = None,
        **payload: Any,
    ):
        data: dict[str, Any] = {"status": "running"}
        if engine_version:
            data["engine_version"] = engine_version
        if config_version:
            data["config_version"] = config_version
        if env:
            data["env"] = env
        if payload:
            data.update(payload)
        return self._emit(f"{self.prefix}.start", payload=data)

    def phase_start(self, phase: str, **payload: Any):
        return self._emit(f"{self.prefix}.phase.start", payload={"phase": phase, **payload})

    def phase_complete(
        self,
        phase: str,
        *,
        status: str,
        duration_ms: int | None = None,
        message: str | None = None,
        **payload: Any,
    ):
        data: dict[str, Any] = {"phase": phase, "status": status}
        if duration_ms is not None:
            data["duration_ms"] = duration_ms
        if message:
            data["message"] = message
        if payload:
            data.update(payload)
        return self._emit(f"{self.prefix}.phase.complete", payload=data)

    def table_summary(self, summary: TableSummary):
        return self._emit(
            f"{self.prefix}.table.summary",
            payload=summary.model_dump(mode="json"),
        )

    def sheet_summary(self, summary: SheetSummary):
        return self._emit(
            f"{self.prefix}.sheet.summary",
            payload=summary.model_dump(mode="json"),
        )

    def file_summary(self, summary: FileSummary):
        return self._emit(
            f"{self.prefix}.file.summary",
            payload=summary.model_dump(mode="json"),
        )

    def validation_issue(self, **payload: Any):
        return self._emit(f"{self.prefix}.validation.issue", payload=payload)

    def validation_summary(self, issues: Iterable[Any]):
        issues_list = list(issues)
        if not issues_list:
            return None

        summary = _aggregate_validation(issues_list)
        return self._emit(f"{self.prefix}.validation.summary", payload=summary)

    def run_summary(self, summary: RunSummary):
        return self._emit(
            f"{self.prefix}.run.summary",
            payload=summary.model_dump(mode="json"),
        )

    def complete(
        self,
        *,
        status: str,
        failure: dict[str, Any] | None = None,
        output_path: str | None = None,
        processed_file: str | None = None,
        events_path: str | None = None,
        error: dict[str, Any] | None = None,
        **payload: Any,
    ):
        artifacts: dict[str, Any] = {}
        if output_path is not None:
            artifacts["output_path"] = output_path
        if processed_file is not None:
            artifacts["processed_file"] = processed_file
        if events_path is not None:
            artifacts["events_path"] = events_path

        completion = RunCompletedPayload(
            status=status,
            failure=failure or error,
            execution=None,
            artifacts=artifacts or None,
            summary=None,
        ).model_dump(exclude_none=True)
        if payload:
            completion.update({k: v for k, v in payload.items() if v is not None})
        return self._emit(f"{self.prefix}.complete", payload=completion)

    # ------------------------------------------------------------------ #
    # Scopes
    # ------------------------------------------------------------------ #

    def config_emitter(self) -> "ConfigEventEmitter":
        return ConfigEventEmitter(
            run=self.run,
            event_sink=self.event_sink,
            source=self.source,
            sequence=self._sequence,
        )


class ConfigEventEmitter(BaseNdjsonEmitter):
    """Emitter surfaced to ade_config code. Events are prefixed with config.*."""

    prefix = "config"

    def custom(self, type_suffix: str, **payload: Any):
        return self._emit(f"{self.prefix}.{type_suffix}", payload=payload or None)


__all__ = ["BaseNdjsonEmitter", "ConfigEventEmitter", "EngineEventEmitter"]
