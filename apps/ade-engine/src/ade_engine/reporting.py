"""Structured logging + events.

The engine can be run in two reporting modes:

- ``text``: human-friendly lines (default; written to stderr)
- ``ndjson``: structured newline-delimited JSON (default; written to stdout)

Inside engine code and config scripts, the API is the same:
- ``logger.<level>(...)`` for log-style messages
- ``event_emitter.emit("event.name", ...)`` for structured events
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, IO, Mapping, Protocol


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Sink(Protocol):
    def write(self, event: dict[str, Any]) -> None: ...


class NdjsonSink:
    def __init__(self, stream: IO[str]) -> None:
        self._stream = stream

    def write(self, event: dict[str, Any]) -> None:
        self._stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        try:
            self._stream.flush()
        except Exception:
            pass


class TextSink(Sink):
    def __init__(self, stream: IO[str]) -> None:
        self._stream = stream

    def write(self, event: dict[str, Any]) -> None:
        ts = event.get("ts") or _utc_now()
        name = event.get("event") or "event"
        message = event.get("message")
        level = event.get("level")
        stage = event.get("stage")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}

        if name == "log":
            logger_name = event.get("logger")
            head = f"[{ts}] {str(level or 'info').upper()}"
            if logger_name:
                head += f" {logger_name}"
            line = head + ": " + str(message or "")
            self._stream.write(line + "\n")

            tb = event.get("traceback")
            if tb:
                self._stream.write(str(tb).rstrip("\n") + "\n")
        else:
            lvl = str(level or "info").upper()
            head = f"[{ts}] {lvl} {name}"
            line = f"{head}: {message}" if message else head

            extras: list[str] = []
            if stage:
                extras.append(f"stage={stage}")

            status = data.get("status")
            if status:
                extras.append(f"status={status}")

            output = data.get("output_file") or data.get("output_path")
            if output and name in {"run.planned", "run.completed"}:
                extras.append(f"output={output}")

            error = data.get("error")
            if isinstance(error, dict):
                code = error.get("code")
                err_stage = error.get("stage")
                err_msg = error.get("message")

                if err_stage and not stage:
                    extras.append(f"stage={err_stage}")

                if code or err_msg:
                    clean_msg = str(err_msg or "").replace("\n", " ").strip()
                    if clean_msg and code:
                        extras.append(f"error={code}: {clean_msg}")
                    elif code:
                        extras.append(f"error={code}")
                    elif clean_msg:
                        extras.append(f"error={clean_msg}")

            if extras:
                line += " (" + ", ".join(extras) + ")"

            self._stream.write(line + "\n")

        try:
            self._stream.flush()
        except Exception:
            pass
class EventEmitter:
    """Structured event emitter used by the CLI/API (dependency-free)."""

    def __init__(self, sink: Sink, *, run_id: str | None = None, meta: Mapping[str, Any] | None = None) -> None:
        self._sink = sink
        self._run_id = str(run_id) if run_id is not None else None
        self._meta = dict(meta or {})

    def child(self, meta: Mapping[str, Any] | None = None) -> "EventEmitter":
        merged = dict(self._meta)
        if meta:
            merged.update(meta)
        return EventEmitter(self._sink, run_id=self._run_id, meta=merged)

    def emit(self, event: str, /, **fields: Any) -> None:
        payload: dict[str, Any] = {"ts": _utc_now(), "event": event}

        if self._run_id:
            payload["run_id"] = self._run_id
        if self._meta:
            payload["meta"] = dict(self._meta)

        # Common top-level fields
        for key in ("message", "level", "stage", "logger", "exc_type", "exc", "traceback"):
            if key in fields and fields[key] is not None:
                payload[key] = fields.pop(key)

        if fields:
            payload["data"] = fields

        try:
            self._sink.write(payload)
        except Exception:
            # Reporting should never crash a run.
            pass

    # Backwards-compatible alias some scripts use.
    def custom(self, event: str, /, **fields: Any) -> None:
        self.emit(event, **fields)

    def config_emitter(self) -> "EventEmitter":
        return self


class EmitToSinkHandler(logging.Handler):
    """Convert standard logging records into structured ``log`` events."""

    def __init__(self, emitter: EventEmitter) -> None:
        super().__init__()
        self._emitter = emitter

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:
            message = str(getattr(record, "msg", ""))

        payload: dict[str, Any] = {
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": message,
        }

        if record.exc_info:
            exc_type, exc, _ = record.exc_info
            payload["exc_type"] = getattr(exc_type, "__name__", None)
            payload["exc"] = str(exc)
            try:
                payload["traceback"] = "".join(traceback.format_exception(*record.exc_info))
            except Exception:
                pass

        self._emitter.emit("log", **payload)


@dataclass
class Reporter:
    logger: logging.Logger
    emitter: EventEmitter
    _handle: IO[str] | None = None

    def close(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            handle.close()
        except Exception:
            pass

    def __enter__(self) -> "Reporter":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()


def build_reporting(
    fmt: Any,
    *,
    run_id: str,
    meta: Mapping[str, Any] | None = None,
    file_path: Path | None = None,
    level: int = logging.INFO,
) -> Reporter:
    """Create a logger + event emitter pair.

    - If ``file_path`` is provided, logs/events are written there.
    - Otherwise: ``text`` -> stderr, ``ndjson`` -> stdout.
    """

    fmt_value = getattr(fmt, "value", fmt)
    fmt_value = str(fmt_value or "text").strip().lower()
    if fmt_value not in {"text", "ndjson"}:
        raise ValueError("fmt must be 'text' or 'ndjson'")

    handle: IO[str] | None = None
    if file_path is not None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        handle = file_path.open("w", encoding="utf-8", newline="\n")
        stream: IO[str] = handle
    else:
        stream = sys.stdout if fmt_value == "ndjson" else sys.stderr

    sink: Sink = NdjsonSink(stream) if fmt_value == "ndjson" else TextSink(stream)
    emitter = EventEmitter(sink, run_id=run_id, meta=meta)

    logger = logging.getLogger(f"ade_engine.run.{run_id}")
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False
    handler = EmitToSinkHandler(emitter)
    handler.setLevel(level)
    logger.addHandler(handler)

    return Reporter(logger=logger, emitter=emitter, _handle=handle)


@contextmanager
def protect_stdout(*, enabled: bool = True):
    """Redirect stdout to stderr to keep NDJSON output clean."""
    if not enabled:
        yield
        return
    with redirect_stdout(sys.stderr):
        yield


__all__ = ["EventEmitter", "Reporter", "build_reporting", "protect_stdout"]
