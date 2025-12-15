"""
ade_engine/logging.py

Minimal structured, run-scoped logging for ADE (stdlib logging + Pydantic v2).

Event model
-----------
Each log entry is a structured event:

    {
        "event_id": "<uuid4 hex>",
        "engine_run_id": "<uuid4 hex>",
        "timestamp": "<RFC3339 UTC>",
        "level": "info" | "debug" | "warning" | "error" | "critical",
        "event": "<namespaced.event.name>",
        "message": "<human-readable message>",
        "data": { ... optional structured payload ... },
        "error": {
            "type": "<ExceptionType>",
            "message": "<exception message>",
            "stack_trace": "<formatted traceback>"
        }
    }

Schema policy
-------------
- engine.* events are strict (must be registered; payload validated if a schema exists)
- engine.config.* is open (any event/payload allowed), but if a schema is registered, validate it
- other namespaces are open, with optional validation if registered

Pydantic notes
--------------
- Strict engine payloads use Pydantic models with `extra="forbid"`.
- Validation uses `Model.model_validate(payload, strict=True)` and
  `model_dump(mode="python", exclude_none=True)` for performance + clean output.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
import logging
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, ValidationError

ENGINE_NAMESPACE = "engine"
CONFIG_NAMESPACE = "engine.config"

VALID_LOG_FORMATS = {"text", "ndjson", "json"}  # "json" is an alias for ndjson
DEFAULT_EVENT = "log"  # fallback event for plain log lines

EventData: TypeAlias = Mapping[str, Any]
PayloadModel: TypeAlias = type[BaseModel] | None


# ---------------------------------------------------------------------------
# Engine event payload schemas (strict for engine.*; open for engine.config.*)
# ---------------------------------------------------------------------------

class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunStartedPayload(StrictPayload):
    input_file: str | None
    config_package: str


class RunPlannedPayload(StrictPayload):
    output_file: str
    output_dir: str
    logs_file: str | None = None
    logs_dir: str | None = None


class WorkbookStartedPayload(StrictPayload):
    sheet_count: int


class SheetStartedPayload(StrictPayload):
    sheet_name: str
    sheet_index: int


class SheetTablesDetectedPayload(StrictPayload):
    sheet_name: str
    sheet_index: int
    input_file: str
    row_count: int
    table_count: int
    tables: list[dict[str, Any]]


class TableDetectedPayload(StrictPayload):
    sheet_name: str
    sheet_index: int
    table_index: int
    input_file: str
    region: dict[str, Any]
    row_count: int
    column_count: int


class TableExtractedPayload(StrictPayload):
    sheet_name: str
    table_index: int
    row_count: int
    col_count: int


class TableMappedPayload(StrictPayload):
    sheet_name: str
    table_index: int
    mapped_fields: int
    total_fields: int
    passthrough_fields: int


class TableMappingPatchedPayload(StrictPayload):
    sheet_name: str
    table_index: int


class TableNormalizedPayload(StrictPayload):
    sheet_name: str
    table_index: int
    row_count: int
    issue_count: int
    issues_by_severity: dict[str, int]


class TableWrittenPayload(StrictPayload):
    sheet_name: str
    table_index: int
    output_range: str


class DetectorResult(StrictPayload):
    name: str
    scores: dict[str, float]
    duration_ms: float


class RowClassificationResult(StrictPayload):
    row_kind: str
    score: float
    considered_row_kinds: list[str]


class ColumnClassificationResult(StrictPayload):
    field: str
    score: float
    considered_fields: list[str]


class RowClassificationPayload(StrictPayload):
    sheet_name: str
    row_index: int
    detectors: list[DetectorResult]
    scores: dict[str, float]
    classification: RowClassificationResult


class RowDetectorResultPayload(StrictPayload):
    sheet_name: str
    row_index: int
    detector: DetectorResult


class ColumnDetectorResultPayload(StrictPayload):
    sheet_name: str
    column_index: int
    detector: DetectorResult


class ColumnClassificationPayload(StrictPayload):
    sheet_name: str
    column_index: int
    detectors: list[DetectorResult]
    scores: dict[str, float]
    classification: ColumnClassificationResult


class RunCompletedPayload(StrictPayload):
    status: str
    started_at: str
    completed_at: str
    stage: str | None = None
    output_path: str | None = None
    error: dict[str, Any] | None = None


# Registry:
# - Missing key: unregistered (strict engine.* will error; others are open)
# - Value None: known-but-freeform payload (no validation)
# - Value BaseModel: validate + normalize payload through model
ENGINE_EVENT_SCHEMAS: dict[str, PayloadModel] = {
    f"{ENGINE_NAMESPACE}.{DEFAULT_EVENT}": None,

    f"{ENGINE_NAMESPACE}.run.started": RunStartedPayload,
    f"{ENGINE_NAMESPACE}.run.planned": RunPlannedPayload,
    f"{ENGINE_NAMESPACE}.run.completed": RunCompletedPayload,

    f"{ENGINE_NAMESPACE}.workbook.started": WorkbookStartedPayload,

    f"{ENGINE_NAMESPACE}.sheet.started": SheetStartedPayload,
    f"{ENGINE_NAMESPACE}.sheet.tables_detected": SheetTablesDetectedPayload,

    f"{ENGINE_NAMESPACE}.table.detected": TableDetectedPayload,
    f"{ENGINE_NAMESPACE}.table.extracted": TableExtractedPayload,
    f"{ENGINE_NAMESPACE}.table.mapped": TableMappedPayload,
    f"{ENGINE_NAMESPACE}.table.mapping_patched": TableMappingPatchedPayload,
    f"{ENGINE_NAMESPACE}.table.normalized": TableNormalizedPayload,
    f"{ENGINE_NAMESPACE}.table.written": TableWrittenPayload,

    # Debug/telemetry events (payloads are open/optional)
    f"{ENGINE_NAMESPACE}.settings.effective": None,
    # Detector results
    f"{ENGINE_NAMESPACE}.detector.row_result": RowDetectorResultPayload,
    f"{ENGINE_NAMESPACE}.detector.column_result": ColumnDetectorResultPayload,
    f"{ENGINE_NAMESPACE}.row_detector.summary": None,
    f"{ENGINE_NAMESPACE}.row_classification": RowClassificationPayload,
    f"{ENGINE_NAMESPACE}.column_detector.candidate": None,
    f"{ENGINE_NAMESPACE}.column_detector.summary": None,
    f"{ENGINE_NAMESPACE}.column_classification": ColumnClassificationPayload,
    # Transform/validation results
    f"{ENGINE_NAMESPACE}.transform.result": None,
    f"{ENGINE_NAMESPACE}.validation.result": None,
    f"{ENGINE_NAMESPACE}.transform.derived_merge": None,
    f"{ENGINE_NAMESPACE}.validation.summary": None,
    f"{ENGINE_NAMESPACE}.transform.overwrite": None,
    f"{ENGINE_NAMESPACE}.hook.start": None,
    f"{ENGINE_NAMESPACE}.hook.end": None,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rfc3339_utc(created: float) -> str:
    return (
        datetime.fromtimestamp(created, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _truncate(value: Any, *, max_len: int = 120) -> str:
    text = str(value)
    return text if len(text) <= max_len else (text[: max_len - 1] + "…")


def normalize_dotpath(value: str | None) -> str:
    return "" if not value else value.strip().strip(".")


def qualify_event_name(event_name: str, namespace: str) -> str:
    """
    Fully qualify `event_name` under `namespace`.

    - If already under namespace, keep it
    - If it starts with the same root (e.g. "engine.") graft it under namespace
    - Else prefix with namespace
    """
    name = normalize_dotpath(event_name)
    ns = normalize_dotpath(namespace)

    if not ns:
        return name or "invalid_event"
    if not name:
        return f"{ns}.invalid_event"
    if name == ns or name.startswith(f"{ns}."):
        return name

    root = ns.split(".", 1)[0]
    if root and name.startswith(f"{root}."):
        return f"{ns}.{name[len(root) + 1:]}"

    return f"{ns}.{name}"


def _is_engine_event(full_event: str) -> bool:
    return full_event == ENGINE_NAMESPACE or full_event.startswith(f"{ENGINE_NAMESPACE}.")


def _is_config_event(full_event: str) -> bool:
    return full_event == CONFIG_NAMESPACE or full_event.startswith(f"{CONFIG_NAMESPACE}.")


def _validate_payload(full_event: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Validate/normalize payload based on policy.

    - Strict: engine.* except engine.config.* must be registered
    - Open:  engine.config.* (validate only if registered)
    - Open:  other namespaces (validate only if registered)
    """
    if _is_engine_event(full_event) and not _is_config_event(full_event):
        if full_event not in ENGINE_EVENT_SCHEMAS:
            raise ValueError(f"Unknown engine event '{full_event}' (add to ENGINE_EVENT_SCHEMAS)")
        schema = ENGINE_EVENT_SCHEMAS[full_event]
    else:
        schema = ENGINE_EVENT_SCHEMAS.get(full_event)  # optional validation

    if schema is None:
        return payload

    try:
        model = schema.model_validate(payload, strict=True)
    except ValidationError as e:
        raise ValueError(f"Invalid payload for event '{full_event}': {e}") from e

    # exclude_none keeps logs compact; flip to False if you want explicit nulls
    return model.model_dump(mode="python", exclude_none=True)


# ---------------------------------------------------------------------------
# Structured formatters (NDJSON + text)
# ---------------------------------------------------------------------------

class _StructuredFormatter(logging.Formatter):
    def _to_event_record(self, record: logging.LogRecord) -> dict[str, Any]:
        # These are injected by RunLogger.process; fallbacks keep formatters safe.
        event_id = getattr(record, "event_id", None) or uuid.uuid4().hex
        engine_run_id = getattr(record, "engine_run_id", None) or ""
        event = getattr(record, "event", None) or DEFAULT_EVENT
        data = getattr(record, "data", None)

        out: dict[str, Any] = {
            "event_id": str(event_id),
            "engine_run_id": str(engine_run_id),
            "timestamp": _rfc3339_utc(record.created),
            "level": record.levelname.lower(),
            "event": str(event),
            "message": record.getMessage(),
        }

        if isinstance(data, Mapping) and data:
            out["data"] = dict(data)

        if record.exc_info:
            exc_type, exc, _tb = record.exc_info
            out["error"] = {
                "type": getattr(exc_type, "__name__", str(exc_type)),
                "message": "" if exc is None else str(exc),
                "stack_trace": self.formatException(record.exc_info),
            }

        return out


class NdjsonFormatter(_StructuredFormatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload = self._to_event_record(record)
        try:
            return json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
        except Exception as e:  # pragma: no cover
            fallback = {
                "event_id": payload.get("event_id") or uuid.uuid4().hex,
                "engine_run_id": payload.get("engine_run_id") or "",
                "timestamp": _rfc3339_utc(record.created),
                "level": "error",
                "event": f"{ENGINE_NAMESPACE}.logging.serialization_failed",
                "message": f"Failed to serialize log record: {e}",
            }
            return json.dumps(fallback, ensure_ascii=False, default=str, separators=(",", ":"))


class TextFormatter(_StructuredFormatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload = self._to_event_record(record)
        ts = payload["timestamp"]
        lvl = payload["level"].upper()
        event = payload.get("event") or ""
        msg = payload["message"]

        head = f"[{ts}] {lvl} {event}"
        if msg and msg != event:
            head += f": {msg}"

        data = payload.get("data")
        if isinstance(data, Mapping) and data:
            items: list[str] = []
            for key in sorted(data, key=str)[:8]:
                items.append(f"{key}={_truncate(data[key])}")
            if len(data) > 8:
                items.append("…")
            head += " (" + ", ".join(items) + ")"

        err = payload.get("error")
        if isinstance(err, Mapping):
            stack = err.get("stack_trace")
            if stack:
                head += "\n" + str(stack).rstrip("\n")

        return head


# ---------------------------------------------------------------------------
# RunLogger
# ---------------------------------------------------------------------------

class RunLogger(logging.LoggerAdapter):
    """
    LoggerAdapter that:
    - stamps each record with engine_run_id + event_id
    - adds a default event for plain log lines
    - provides .event() for domain events (Pydantic validation for strict engine events)
    """

    def __init__(
        self,
        logger: logging.Logger,
        *,
        namespace: str = ENGINE_NAMESPACE,
        engine_run_id: str | None = None,
    ) -> None:
        self._namespace = normalize_dotpath(namespace)
        self._engine_run_id = engine_run_id or uuid.uuid4().hex
        super().__init__(logger, {"namespace": self._namespace, "engine_run_id": self._engine_run_id})

    @property
    def namespace(self) -> str:
        return str((self.extra or {}).get("namespace", ""))

    @property
    def engine_run_id(self) -> str:
        return self._engine_run_id

    def with_namespace(self, namespace: str) -> "RunLogger":
        return RunLogger(self.logger, namespace=namespace, engine_run_id=self._engine_run_id)

    def process(self, msg: Any, kwargs: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        caller_extra = kwargs.pop("extra", None)
        extra = dict(self.extra or {})

        if caller_extra is not None:
            if not isinstance(caller_extra, Mapping):
                raise TypeError("logging 'extra' must be a mapping")
            extra.update(caller_extra)

        # Stable run id (caller can't override).
        extra["engine_run_id"] = self._engine_run_id

        # Normalize namespace.
        ns = normalize_dotpath(str(extra.get("namespace") or ""))
        if ns:
            extra["namespace"] = ns
        else:
            extra.pop("namespace", None)

        # Per-record id.
        extra["event_id"] = str(extra.get("event_id") or uuid.uuid4().hex)

        # Default event for plain log lines.
        extra.setdefault("event", qualify_event_name(DEFAULT_EVENT, ns) if ns else DEFAULT_EVENT)

        # Normalize `data`.
        data = extra.get("data")
        if data is not None and not isinstance(data, Mapping):
            extra["data"] = {"value": data}

        kwargs["extra"] = extra
        return msg, kwargs

    def event(
        self,
        name: str,
        *,
        message: str | None = None,
        level: int = logging.INFO,
        data: EventData | None = None,
        exc: BaseException | None = None,
        **fields: Any,
    ) -> None:
        if not self.isEnabledFor(level):
            return

        ns = self.namespace
        full_name = qualify_event_name(name, ns) if ns else normalize_dotpath(name) or "invalid_event"

        payload: dict[str, Any] = {}
        if data:
            payload.update(dict(data))
        if fields:
            payload.update(fields)

        payload = _validate_payload(full_name, payload)

        extra: dict[str, Any] = {"event": full_name}
        if payload:
            extra["data"] = payload

        exc_info = (type(exc), exc, exc.__traceback__) if exc is not None else None
        self.log(level, message or full_name, extra=extra, exc_info=exc_info)


class NullLogger(RunLogger):
    """A RunLogger implementation that discards all log/event output."""

    def __init__(
        self,
        *,
        namespace: str = ENGINE_NAMESPACE,
        engine_run_id: str = "null",
    ) -> None:
        base_logger = logging.Logger("ade_engine.null")
        base_logger.addHandler(logging.NullHandler())
        base_logger.propagate = False
        base_logger.disabled = True
        super().__init__(base_logger, namespace=namespace, engine_run_id=engine_run_id)

    def with_namespace(self, namespace: str) -> "NullLogger":
        return NullLogger(namespace=namespace, engine_run_id=self._engine_run_id)

    def __bool__(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# RunLogContext
# ---------------------------------------------------------------------------

@dataclass
class RunLogContext:
    logger: RunLogger
    _base_logger: logging.Logger
    _handlers: list[logging.Handler]

    def close(self) -> None:
        for h in list(self._handlers):
            try:
                self._base_logger.removeHandler(h)
                h.close()
            except Exception:
                pass

    def __enter__(self) -> "RunLogContext":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()


def create_run_logger_context(
    *,
    namespace: str = ENGINE_NAMESPACE,
    log_format: str = "text",
    log_level: int = logging.INFO,
    enable_console_logging: bool = True,
    log_file: Path | None = None,
) -> RunLogContext:
    fmt = (log_format or "text").strip().lower()
    if fmt == "json":
        fmt = "ndjson"
    if fmt not in {"text", "ndjson"}:
        raise ValueError("log_format must be 'text' or 'ndjson' (or 'json')")

    formatter: logging.Formatter = NdjsonFormatter() if fmt == "ndjson" else TextFormatter()

    handlers: list[logging.Handler] = []

    if enable_console_logging:
        h = logging.StreamHandler(sys.stderr)
        h.setLevel(log_level)
        h.setFormatter(formatter)
        handlers.append(h)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        handlers.append(fh)

    run_id = uuid.uuid4().hex
    base_logger = logging.getLogger(f"ade_engine.run.{run_id}")
    base_logger.setLevel(log_level)
    base_logger.handlers.clear()
    base_logger.propagate = False
    for h in handlers:
        base_logger.addHandler(h)

    logger = RunLogger(base_logger, namespace=namespace, engine_run_id=run_id)
    return RunLogContext(logger=logger, _base_logger=base_logger, _handlers=handlers)


__all__ = [
    "ENGINE_NAMESPACE",
    "CONFIG_NAMESPACE",
    "DEFAULT_EVENT",
    "VALID_LOG_FORMATS",
    "ENGINE_EVENT_SCHEMAS",
    "NdjsonFormatter",
    "TextFormatter",
    "RunLogger",
    "NullLogger",
    "RunLogContext",
    "create_run_logger_context",
    "normalize_dotpath",
    "qualify_event_name",
]
