"""Worker loop, run processing, and environment provisioning."""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import random
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import psycopg
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ade_db.engine import (
    assert_tables_exist,
    build_engine,
    build_psycopg_connect_kwargs,
    session_scope,
)
from ade_db.models import EnvironmentStatus, FileKind
from . import db
from .paths import PathManager
from ade_db.schema import REQUIRED_TABLES
from .settings import Settings, get_settings
from ade_storage import build_storage_adapter, ensure_storage_roots

logger = logging.getLogger("ade_worker")

CHANNEL_RUN_QUEUED = "ade_run_queued"
CLAIM_BATCH_SIZE = 5
LISTEN_MAX_BACKOFF_SECONDS = 30.0
NOTIFY_JITTER_MS = 200
_STANDARD_LOG_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
    "taskName",
    "color_message",
}


# --- time / paths ---

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _default_worker_id() -> str:
    host = socket.gethostname() or "worker"
    return f"{host}-{uuid4().hex[:8]}"


class WorkerJsonLogFormatter(logging.Formatter):
    """Render worker logs as JSON objects for container log collectors."""

    _time_format = "%Y-%m-%dT%H:%M:%S"

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        pattern = datefmt or self._time_format
        base = dt.strftime(pattern)
        return f"{base}.{int(record.msecs):03d}Z"

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - std signature
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self._time_format),
            "level": record.levelname,
            "service": "ade-worker",
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


def _setup_logging(level: str, *, log_format: str) -> None:
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        root_logger.handlers = [logging.StreamHandler()]
    else:
        root_logger.handlers = [root_logger.handlers[0]]

    handler = root_logger.handlers[0]
    if log_format == "json":
        handler.setFormatter(WorkerJsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s %(name)s %(message)s"))

    root_logger.setLevel(getattr(logging, level))


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _ensure_runtime_dirs(settings: Settings) -> None:
    ensure_storage_roots(settings)
    _ensure_dir(settings.pip_cache_dir)


# --- LISTEN / NOTIFY ---


def _listen_connect(settings: Settings, *, channel: str) -> psycopg.Connection:
    params = build_psycopg_connect_kwargs(settings)
    conn = psycopg.connect(**params, autocommit=True)
    with conn.cursor() as cur:
        cur.execute(f"LISTEN {channel}")
    return conn


@dataclass(slots=True)
class PgListener:
    settings: Settings
    channel: str = CHANNEL_RUN_QUEUED
    conn: psycopg.Connection | None = None
    backoff: float = 1.0

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
        self.conn = None

    def ensure_connected(self) -> bool:
        if self.conn is not None and not self.conn.closed:
            return True
        try:
            self.conn = _listen_connect(self.settings, channel=self.channel)
            logger.info("run.notify.listen channel=%s", self.channel)
            self.backoff = 1.0
            return True
        except Exception:
            logger.exception("run.notify.listen_failed retry_in=%ss", self.backoff)
            time.sleep(self.backoff + random.random())
            self.backoff = min(LISTEN_MAX_BACKOFF_SECONDS, self.backoff * 2)
            self.conn = None
            return False

    def wait(self, timeout: float) -> bool:
        if timeout <= 0:
            return False
        if not self.ensure_connected():
            return False
        try:
            for _notify in self.conn.notifies(timeout=timeout):
                return True
            return False
        except Exception:
            logger.exception("run.notify.listen_failed retry_in=%ss", self.backoff)
            self.close()
            time.sleep(self.backoff + random.random())
            self.backoff = min(LISTEN_MAX_BACKOFF_SECONDS, self.backoff * 2)
            return False


# --- NDJSON logging + subprocess runner ---

def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventLog:
    """Append-only NDJSON log file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._dir_ready = False
        self._ensure_parent()

    def _ensure_parent(self) -> None:
        if self._dir_ready:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._dir_ready = True

    def append(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self._lock:
            try:
                self._ensure_parent()
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line)
            except FileNotFoundError:
                # Parent directory may have been cleaned up; recreate once.
                self._dir_ready = False
                self._ensure_parent()
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line)

    def emit(
        self,
        *,
        event: str,
        level: str = "info",
        message: str = "",
        data: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        rec: dict[str, Any] = {
            "timestamp": utc_iso(),
            "level": level,
            "event": event,
            "message": message,
            "data": data or {},
        }
        if context:
            rec["context"] = dict(context)
        self.append(rec)


@dataclass(frozen=True, slots=True)
class SubprocessResult:
    exit_code: int
    timed_out: bool
    duration_seconds: float


class HeartbeatLostError(RuntimeError):
    """Raised when a lease heartbeat fails and work should stop."""


class SubprocessRunner:
    def run(
        self,
        cmd: list[str],
        *,
        event_log: EventLog,
        scope: str,
        timeout_seconds: float | None,
        cwd: str | None,
        env: dict[str, str] | None,
        heartbeat: Callable[[], bool] | None = None,
        heartbeat_interval: float = 15.0,
        context: dict[str, Any] | None = None,
        on_json_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> SubprocessResult:
        start = time.monotonic()
        deadline = (start + float(timeout_seconds)) if timeout_seconds is not None else None

        event_log.emit(
            event=f"{scope}.start",
            message="Starting subprocess",
            data={"cmd": cmd, "cwd": cwd or ""},
            context=context,
        )

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=cwd,
            env=env,
            start_new_session=(os.name != "nt"),
        )

        errors: list[BaseException] = []
        timed_out = False

        def drain(stream, stream_name: str) -> None:
            try:
                assert stream is not None
                for raw in iter(stream.readline, ""):
                    line = raw.rstrip("\n")
                    if not line:
                        continue
                    try:
                        obj = json.loads(line) if line.startswith("{") else None
                    except json.JSONDecodeError:
                        obj = None

                    if isinstance(obj, dict) and "event" in obj:
                        if context:
                            obj = dict(obj)
                            obj.setdefault("context", {})
                            if isinstance(obj["context"], dict):
                                obj["context"].update(dict(context))
                            else:
                                obj["context"] = dict(context)
                        event_log.append(obj)
                        if on_json_event:
                            on_json_event(obj)
                    else:
                        event_log.emit(event=f"{scope}.{stream_name}", message=line, context=context)
            except BaseException as exc:
                errors.append(exc)
            finally:
                try:
                    stream.close()  # type: ignore[attr-defined]
                except Exception:
                    pass

        threads = [
            threading.Thread(target=drain, args=(proc.stdout, "stdout"), daemon=True),
            threading.Thread(target=drain, args=(proc.stderr, "stderr"), daemon=True),
        ]
        for t in threads:
            t.start()

        def _call_heartbeat() -> None:
            if not heartbeat:
                return
            try:
                ok = heartbeat()
            except BaseException:
                self._terminate(proc)
                raise
            if ok is False:
                self._terminate(proc)
                raise HeartbeatLostError("Lease heartbeat failed")

        last_hb = 0.0
        if heartbeat:
            _call_heartbeat()
            last_hb = time.monotonic()

        while True:
            if errors:
                raise errors[0]

            now = time.monotonic()

            if heartbeat and (now - last_hb) >= float(heartbeat_interval):
                _call_heartbeat()
                last_hb = now

            if deadline is not None and now >= deadline:
                timed_out = True
                self._terminate(proc)
                break

            rc = proc.poll()
            if rc is not None:
                break

            time.sleep(0.05)

        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._terminate(proc)

        for t in threads:
            t.join(timeout=2)

        if errors:
            raise errors[0]

        duration = max(0.0, time.monotonic() - start)
        exit_code = int(proc.returncode or 0)
        if timed_out:
            exit_code = 124

        event_log.emit(
            event=f"{scope}.complete",
            message="Subprocess finished",
            data={"cmd": cmd, "exit_code": exit_code, "timed_out": timed_out, "duration_seconds": duration},
            context=context,
        )

        return SubprocessResult(exit_code=exit_code, timed_out=timed_out, duration_seconds=duration)

    def _terminate(self, proc: subprocess.Popen) -> None:
        try:
            if os.name != "nt":
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    return
            else:
                proc.terminate()
        except Exception:
            pass

        try:
            proc.wait(timeout=5)
            return
        except Exception:
            pass

        try:
            if os.name != "nt":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except Exception:
            pass


# --- Run results parsing ---

SEVERITIES = ("info", "warning", "error")
MAPPING_STATUSES = ("mapped", "unmapped")


def _as_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _as_str(value: Any) -> str | None:
    if isinstance(value, str):
        candidate = value.strip()
        return candidate or None
    return None


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        candidate = value.strip()
        if candidate and candidate.lstrip("-").isdigit():
            try:
                return int(candidate)
            except ValueError:
                return None
    return None


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        try:
            return float(candidate)
        except ValueError:
            return None
    return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in {"1", "true", "yes", "y", "on"}:
            return True
        if candidate in {"0", "false", "no", "n", "off"}:
            return False
    return None


def _normalize_mapping_status(value: Any) -> str | None:
    status = _as_str(value)
    if status is None:
        return None
    status = status.lower()
    return status if status in MAPPING_STATUSES else None


def _count_findings(findings: list[Any]) -> dict[str, int]:
    counts = {severity: 0 for severity in SEVERITIES}
    for item in findings:
        data = _as_dict(item) or {}
        severity = _as_str(data.get("severity"))
        if severity is None:
            continue
        severity = severity.lower()
        if severity in counts:
            counts[severity] += 1
    return counts


def _metrics_has_values(metrics: dict[str, Any]) -> bool:
    return any(value is not None for value in metrics.values())


def parse_run_metrics(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    scope = _as_str(payload.get("scope"))
    if scope is not None and scope != "run":
        return None

    metrics: dict[str, Any] = {
        "evaluation_outcome": None,
        "evaluation_findings_total": None,
        "evaluation_findings_info": None,
        "evaluation_findings_warning": None,
        "evaluation_findings_error": None,
        "validation_issues_total": None,
        "validation_issues_info": None,
        "validation_issues_warning": None,
        "validation_issues_error": None,
        "validation_max_severity": None,
        "workbook_count": None,
        "sheet_count": None,
        "table_count": None,
        "row_count_total": None,
        "row_count_empty": None,
        "column_count_total": None,
        "column_count_empty": None,
        "column_count_mapped": None,
        "column_count_unmapped": None,
        "field_count_expected": None,
        "field_count_detected": None,
        "field_count_not_detected": None,
        "cell_count_total": None,
        "cell_count_non_empty": None,
    }

    evaluation = _as_dict(payload.get("evaluation")) or {}
    metrics["evaluation_outcome"] = _as_str(evaluation.get("outcome"))
    findings = evaluation.get("findings")
    if isinstance(findings, list):
        metrics["evaluation_findings_total"] = len(findings)
        counts = _count_findings(findings)
        metrics["evaluation_findings_info"] = counts["info"]
        metrics["evaluation_findings_warning"] = counts["warning"]
        metrics["evaluation_findings_error"] = counts["error"]

    validation = _as_dict(payload.get("validation")) or {}
    metrics["validation_issues_total"] = _as_int(validation.get("issues_total"))
    issues_by_severity = _as_dict(validation.get("issues_by_severity")) or {}
    metrics["validation_issues_info"] = _as_int(issues_by_severity.get("info"))
    metrics["validation_issues_warning"] = _as_int(issues_by_severity.get("warning"))
    metrics["validation_issues_error"] = _as_int(issues_by_severity.get("error"))
    metrics["validation_max_severity"] = _as_str(validation.get("max_severity"))

    counts = _as_dict(payload.get("counts")) or {}
    metrics["workbook_count"] = _as_int(counts.get("workbooks"))
    metrics["sheet_count"] = _as_int(counts.get("sheets"))
    metrics["table_count"] = _as_int(counts.get("tables"))

    rows = _as_dict(counts.get("rows")) or {}
    metrics["row_count_total"] = _as_int(rows.get("total"))
    metrics["row_count_empty"] = _as_int(rows.get("empty"))

    columns = _as_dict(counts.get("columns")) or {}
    metrics["column_count_total"] = _as_int(columns.get("total"))
    metrics["column_count_empty"] = _as_int(columns.get("empty"))
    metrics["column_count_mapped"] = _as_int(columns.get("mapped"))
    metrics["column_count_unmapped"] = _as_int(columns.get("unmapped"))

    fields = _as_dict(counts.get("fields")) or {}
    metrics["field_count_expected"] = _as_int(fields.get("expected"))
    metrics["field_count_detected"] = _as_int(fields.get("detected"))
    metrics["field_count_not_detected"] = _as_int(fields.get("not_detected"))

    cells = _as_dict(counts.get("cells")) or {}
    metrics["cell_count_total"] = _as_int(cells.get("total"))
    metrics["cell_count_non_empty"] = _as_int(cells.get("non_empty"))

    return metrics if _metrics_has_values(metrics) else None


def parse_run_fields(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    scope = _as_str(payload.get("scope"))
    if scope is not None and scope != "run":
        return []

    rows: list[dict[str, Any]] = []
    fields = payload.get("fields")
    if not isinstance(fields, list):
        return rows

    for item in fields:
        data = _as_dict(item)
        if not data:
            continue
        field_name = _as_str(data.get("field"))
        if not field_name:
            continue
        detected = _as_bool(data.get("detected"))
        if detected is None:
            continue
        occurrences = _as_dict(data.get("occurrences")) or {}
        rows.append(
            {
                "field": field_name,
                "label": _as_str(data.get("label")),
                "detected": detected,
                "best_mapping_score": _as_float(data.get("best_mapping_score")),
                "occurrences_tables": _as_int(occurrences.get("tables")) or 0,
                "occurrences_columns": _as_int(occurrences.get("columns")) or 0,
            }
        )

    return rows


def parse_run_table_columns(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    scope = _as_str(payload.get("scope"))
    if scope is not None and scope != "run":
        return []

    rows: list[dict[str, Any]] = []
    workbooks = payload.get("workbooks")
    if not isinstance(workbooks, list):
        return rows

    for workbook in workbooks:
        workbook_data = _as_dict(workbook) or {}
        workbook_locator = _as_dict(workbook_data.get("locator")) or {}
        workbook_info = _as_dict(workbook_locator.get("workbook")) or {}
        workbook_index = _as_int(workbook_info.get("index"))
        workbook_name = _as_str(workbook_info.get("name"))
        if workbook_index is None or not workbook_name:
            continue

        sheets = workbook_data.get("sheets")
        if not isinstance(sheets, list):
            continue
        for sheet in sheets:
            sheet_data = _as_dict(sheet) or {}
            sheet_locator = _as_dict(sheet_data.get("locator")) or {}
            sheet_info = _as_dict(sheet_locator.get("sheet")) or {}
            sheet_index = _as_int(sheet_info.get("index"))
            sheet_name = _as_str(sheet_info.get("name"))
            if sheet_index is None or not sheet_name:
                continue

            tables = sheet_data.get("tables")
            if not isinstance(tables, list):
                continue
            for table in tables:
                table_data = _as_dict(table) or {}
                table_locator = _as_dict(table_data.get("locator")) or {}
                table_info = _as_dict(table_locator.get("table")) or {}
                table_index = _as_int(table_info.get("index"))
                if table_index is None:
                    continue

                structure = _as_dict(table_data.get("structure")) or {}
                columns = structure.get("columns")
                if not isinstance(columns, list):
                    continue
                for column in columns:
                    column_data = _as_dict(column) or {}
                    column_index = _as_int(column_data.get("index"))
                    if column_index is None:
                        continue

                    mapping = _as_dict(column_data.get("mapping")) or {}
                    mapping_status = _normalize_mapping_status(mapping.get("status"))
                    if mapping_status is None:
                        continue

                    header = _as_dict(column_data.get("header")) or {}
                    rows.append(
                        {
                            "workbook_index": workbook_index,
                            "workbook_name": workbook_name,
                            "sheet_index": sheet_index,
                            "sheet_name": sheet_name,
                            "table_index": table_index,
                            "column_index": column_index,
                            "header_raw": _as_str(header.get("raw")),
                            "header_normalized": _as_str(header.get("normalized")),
                            "non_empty_cells": _as_int(column_data.get("non_empty_cells")) or 0,
                            "mapping_status": mapping_status,
                            "mapped_field": _as_str(mapping.get("field")),
                            "mapping_score": _as_float(mapping.get("score")),
                            "mapping_method": _as_str(mapping.get("method")),
                            "unmapped_reason": _as_str(mapping.get("unmapped_reason")),
                        }
                    )

    return rows


# --- Run options + command building ---

@dataclass(slots=True)
class RunOptions:
    validate_only: bool = False
    dry_run: bool = False
    log_level: str = "INFO"
    input_sheet_names: list[str] = None  # type: ignore[assignment]
    active_sheet_only: bool = False
    max_findings_per_sheet: int | None = None
    extra_engine_args: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.input_sheet_names = self.input_sheet_names or []
        self.extra_engine_args = self.extra_engine_args or []


def _json_loads(value: Any) -> Any:
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return value


def _json_loads_dict(value: Any) -> dict[str, Any]:
    obj = _json_loads(value)
    return obj if isinstance(obj, dict) else {}


def _as_str_list(v: Any) -> list[str]:
    if isinstance(v, list):
        out: list[str] = []
        for item in v:
            s = _as_str(item)
            if s:
                out.append(s)
        return out
    if isinstance(v, str):
        return [v.strip()] if v.strip() else []
    return []


def parse_run_options(raw: Any, *, default_log_level: str) -> RunOptions:
    opts = _json_loads_dict(raw)
    return RunOptions(
        validate_only=bool(_as_bool(opts.get("validate_only") or opts.get("validation_only")) or False),
        dry_run=bool(_as_bool(opts.get("dry_run")) or False),
        log_level=(_as_str(opts.get("log_level")) or default_log_level).upper(),
        input_sheet_names=_as_str_list(opts.get("input_sheet_names")),
        active_sheet_only=bool(_as_bool(opts.get("active_sheet_only")) or False),
        max_findings_per_sheet=_as_int(opts.get("max_findings_per_sheet")),
        extra_engine_args=_as_str_list(opts.get("engine_args") or opts.get("extra_args")),
    )


def _parse_input_sheet_names(value: Any) -> list[str]:
    payload = _json_loads(value)
    return _as_str_list(payload)


def engine_config_validate_cmd(*, python_bin: Path, config_dir: Path, log_level: str) -> list[str]:
    return [
        str(python_bin),
        "-m",
        "ade_engine",
        "config",
        "validate",
        "--config-package",
        str(config_dir),
        "--log-format",
        "ndjson",
        "--log-level",
        log_level.upper(),
    ]


def engine_process_file_cmd(
    *,
    python_bin: Path,
    input_path: Path,
    output_dir: Path,
    config_dir: Path,
    options: RunOptions,
    sheet_names: list[str],
) -> list[str]:
    cmd = [
        str(python_bin),
        "-m",
        "ade_engine",
        "process",
        "file",
        "--input",
        str(input_path),
        "--output-dir",
        str(output_dir),
        "--config-package",
        str(config_dir),
        "--log-format",
        "ndjson",
        "--log-level",
        options.log_level.upper(),
    ]
    if options.max_findings_per_sheet is not None and options.max_findings_per_sheet >= 0:
        cmd.extend(["--max-findings-per-sheet", str(options.max_findings_per_sheet)])
    if options.active_sheet_only:
        cmd.append("--active-sheet-only")
    else:
        for sheet in sheet_names:
            s = str(sheet).strip()
            if s:
                cmd.extend(["--input-sheet", s])
    cmd.extend(options.extra_engine_args or [])
    return cmd


def _execution_payload(started_at: datetime, completed_at: datetime) -> dict[str, Any]:
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    duration_ms = max(0, int((completed_at - started_at).total_seconds() * 1000))
    return {
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_ms": duration_ms,
    }


def _emit_run_complete(
    event_log: EventLog,
    *,
    status: str,
    message: str,
    context: dict[str, Any],
    started_at: datetime,
    completed_at: datetime,
    exit_code: int | None,
    error_message: str | None = None,
    output_path: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "status": status,
        "execution": _execution_payload(started_at, completed_at),
    }
    if exit_code is not None:
        payload["exit_code"] = exit_code
    if error_message:
        payload["error_message"] = error_message
    if output_path:
        payload["output_path"] = output_path

    level = "error" if status == "failed" else "info"
    event_log.emit(event="run.complete", level=level, message=message, data=payload, context=context)


def _extract_output_path(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    outputs = payload.get("outputs")
    if not isinstance(outputs, dict):
        return None
    normalized = outputs.get("normalized")
    if not isinstance(normalized, dict):
        return None
    path = normalized.get("path")
    return str(path) if isinstance(path, str) and path.strip() else None


def _relative_to_dir(base: Path, path: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return None


def _normalize_output_path(raw: str | None, *, run_dir: Path) -> str | None:
    if not raw:
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (run_dir / candidate).resolve()
    return _relative_to_dir(run_dir, candidate)


def _infer_output_path(output_dir: Path, *, run_dir: Path) -> str | None:
    if not output_dir.exists():
        return None
    normalized = output_dir / "normalized.xlsx"
    relative = _relative_to_dir(run_dir, normalized)
    if relative and normalized.is_file():
        return relative
    for path in output_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = _relative_to_dir(run_dir, path)
        if relative:
            return relative
    return None


# --- Worker ---

@dataclass(slots=True)
class EnvBuildResult:
    success: bool
    run_lost: bool
    error_message: str | None


@dataclass(slots=True)
class Worker:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    worker_id: str
    paths: PathManager
    runner: SubprocessRunner
    storage: Any

    def _pip_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        env["PIP_NO_INPUT"] = "1"
        env["PIP_PROGRESS_BAR"] = "off"
        env["PIP_CACHE_DIR"] = str(self.paths.pip_cache_dir())
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def _install_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["UV_CACHE_DIR"] = str(self.paths.pip_cache_dir())
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def _uv_bin(self) -> str:
        uv_bin = shutil.which("uv")
        if not uv_bin:
            raise RuntimeError("uv not found on PATH; install ade-worker dependencies with uv available")
        return uv_bin

    def _retry_at(self, claim: db.RunClaim, now: datetime) -> datetime | None:
        if claim.attempt_count < claim.max_attempts:
            delay = self.settings.backoff_seconds(claim.attempt_count)
            return now + timedelta(seconds=int(delay))
        return None

    def _heartbeat_run(self, *, run_id: str, now: datetime | None = None) -> bool:
        timestamp = now or utcnow()
        with session_scope(self.session_factory) as session:
            return db.heartbeat_run(
                session,
                run_id=run_id,
                worker_id=self.worker_id,
                now=timestamp,
                lease_seconds=int(self.settings.worker_lease_seconds),
            )

    def _upload_run_log(self, *, workspace_id: str, run_id: str) -> None:
        log_path = self.paths.run_event_log_path(workspace_id, run_id)
        if not log_path.exists():
            return
        blob_name = f"{workspace_id}/runs/{run_id}/logs/events.ndjson"
        try:
            self.storage.upload_path(blob_name, log_path)
        except Exception as exc:
            logger.warning("run.logs.upload_failed run_id=%s error=%s", run_id, exc)

    def _cleanup_run_dir(self, *, run_dir: Path, workspace_id: str, run_id: str) -> None:
        try:
            run_root = self.paths.runs_root(workspace_id).resolve()
            run_dir_resolved = run_dir.resolve()
            run_dir_resolved.relative_to(run_root)
        except Exception:
            logger.warning("run.dir.cleanup_skipped run_id=%s path=%s", run_id, run_dir)
            return

        if not run_dir.exists():
            return
        try:
            shutil.rmtree(run_dir)
        except Exception as exc:
            logger.warning(
                "run.dir.cleanup_failed run_id=%s workspace_id=%s error=%s",
                run_id,
                workspace_id,
                exc,
            )


    def _build_environment(
        self,
        *,
        env: dict[str, Any],
        env_id: str,
        run_claim: db.RunClaim | None,
    ) -> EnvBuildResult:
        workspace_id = str(env["workspace_id"])
        configuration_id = str(env["configuration_id"])
        deps_digest = str(env["deps_digest"])
        env_root = self.paths.environment_root(
            workspace_id,
            configuration_id,
            deps_digest,
            env_id,
        )
        venv_dir = self.paths.environment_venv_dir(
            workspace_id,
            configuration_id,
            deps_digest,
            env_id,
        )
        event_log = EventLog(
            self.paths.environment_event_log_path(
                workspace_id,
                configuration_id,
                deps_digest,
                env_id,
            )
        )
        ctx = {
            "environment_id": env_id,
            "workspace_id": workspace_id,
            "configuration_id": configuration_id,
            "deps_digest": deps_digest,
        }

        if env_root.exists():
            shutil.rmtree(env_root, ignore_errors=True)
        _ensure_dir(env_root)

        event_log.emit(event="environment.start", message="Starting environment build", context=ctx)

        deadline = time.monotonic() + float(self.settings.worker_env_build_timeout_seconds)
        install_env = self._install_env()
        uv_bin = self._uv_bin()
        last_exit_code: int | None = None
        run_lost = False

        def remaining() -> float:
            return max(0.1, deadline - time.monotonic())

        def heartbeat() -> bool:
            nonlocal run_lost
            if run_claim:
                ok_run = self._heartbeat_run(run_id=run_claim.id)
                if not ok_run:
                    run_lost = True
                    return False
            return True

        try:
            create_cmd = [uv_bin, "venv", "--python", os.fspath(sys.executable), str(venv_dir)]
            res = self.runner.run(
                create_cmd,
                event_log=event_log,
                scope="environment.venv",
                timeout_seconds=remaining(),
                cwd=None,
                env=install_env,
                heartbeat=heartbeat,
                heartbeat_interval=max(1.0, self.settings.worker_lease_seconds / 3),
                context=ctx,
            )
            last_exit_code = res.exit_code
            if res.exit_code != 0:
                raise RuntimeError(f"venv creation failed (exit {res.exit_code})")

            python_bin = self.paths.python_in_venv(venv_dir)
            if not python_bin.exists():
                raise RuntimeError(f"venv python missing: {python_bin}")

            config_dir = self.paths.config_package_dir(workspace_id, configuration_id)
            if not config_dir.exists():
                raise RuntimeError(f"config package dir missing: {config_dir}")

            res = self.runner.run(
                [uv_bin, "pip", "install", "--python", str(python_bin), "-e", str(config_dir)],
                event_log=event_log,
                scope="environment.config",
                timeout_seconds=remaining(),
                cwd=None,
                env=install_env,
                heartbeat=heartbeat,
                heartbeat_interval=max(1.0, self.settings.worker_lease_seconds / 3),
                context=ctx,
            )
            last_exit_code = res.exit_code
            if res.exit_code != 0:
                raise RuntimeError(f"config install failed (exit {res.exit_code})")

            python_version = _run_capture_text([str(python_bin), "--version"])
            try:
                engine_version = subprocess.check_output(
                    [str(python_bin), "-c", "import ade_engine; print(getattr(ade_engine, '__version__', 'unknown'))"],
                    text=True,
                ).strip()
            except Exception:
                engine_version = None

            event_log.emit(
                event="environment.versions",
                message=f"python={python_version} engine={engine_version or 'unknown'}",
                context=ctx,
            )

            finished_at = utcnow()
            with session_scope(self.session_factory) as session:
                ok = db.ack_environment_success(
                    session,
                    env_id=env_id,
                    now=finished_at,
                )
                if not ok:
                    event_log.emit(
                        event="environment.lost_claim",
                        level="warning",
                        message="Environment status changed before completion",
                        context=ctx,
                    )
                    return EnvBuildResult(False, False, "Environment status changed before completion")

                db.record_environment_metadata(
                    session,
                    env_id=env_id,
                    now=finished_at,
                    python_interpreter=str(python_bin),
                    python_version=python_version,
                    engine_version=engine_version,
                )

            event_log.emit(event="environment.complete", message="Environment ready", context=ctx)
            return EnvBuildResult(True, False, None)

        except HeartbeatLostError:
            event_log.emit(
                event="environment.lost_claim",
                level="warning",
                message="Lease expired before environment build finished",
                context=ctx,
            )
            finished_at = utcnow()
            with session_scope(self.session_factory) as session:
                db.ack_environment_failure(
                    session,
                    env_id=env_id,
                    now=finished_at,
                    error_message="Environment build interrupted (run lease lost)",
                )
            return EnvBuildResult(False, run_lost, "Lease expired")
        except Exception as exc:
            err = str(exc)
            logger.exception("environment build failed: %s", err)

            finished_at = utcnow()
            exit_code = last_exit_code or 1

            with session_scope(self.session_factory) as session:
                ok = db.ack_environment_failure(
                    session,
                    env_id=env_id,
                    now=finished_at,
                    error_message=err,
                )
                if not ok:
                    event_log.emit(
                        event="environment.lost_claim",
                        level="warning",
                        message="Environment status changed before failure ack",
                        context=ctx,
                    )
                    return EnvBuildResult(False, False, err)

                db.record_environment_metadata(
                    session,
                    env_id=env_id,
                    now=finished_at,
                    python_interpreter=None,
                    python_version=None,
                    engine_version=None,
                )

            event_log.emit(
                event="environment.failed",
                level="error",
                message=f"{err} (exit {exit_code})",
                context=ctx,
            )
            return EnvBuildResult(False, False, err)

    def _ensure_environment_ready(
        self,
        *,
        run: dict[str, Any],
        run_claim: db.RunClaim,
        now: datetime,
    ) -> tuple[dict[str, Any] | None, str | None, bool]:
        with session_scope(self.session_factory) as session:
            env = db.ensure_environment(session, run=run, now=now)
        if not env:
            return None, "Environment missing", False

        status = env.get("status")
        if status == EnvironmentStatus.READY:
            return env, None, False
        if status is None or not isinstance(status, EnvironmentStatus):
            return None, f"Invalid environment status: {status!r}", False

        env_id = str(env["id"])
        lock_key = (
            f"{env['workspace_id']}:{env['configuration_id']}:{env['engine_spec']}:{env['deps_digest']}"
        )

        lock_conn = self.engine.connect()
        got_lock = False
        try:
            while True:
                got_lock = db.try_advisory_lock(lock_conn, key=lock_key)
                if got_lock:
                    break
                if run_claim:
                    ok = self._heartbeat_run(run_id=run_claim.id)
                    if not ok:
                        return None, None, True
                time.sleep(0.2 + random.random() * 0.8)

            with self.session_factory() as session:
                env = db.load_environment(session, env_id)
            if not env:
                return None, "Environment missing", False
            status = env.get("status")
            if status == EnvironmentStatus.READY:
                return env, None, False
            if status is None or not isinstance(status, EnvironmentStatus):
                return None, f"Invalid environment status: {status!r}", False

            with session_scope(self.session_factory) as session:
                db.mark_environment_building(session, env_id=env_id, now=now)

            build = self._build_environment(env=env, env_id=env_id, run_claim=run_claim)

            if build.run_lost:
                return None, None, True

            with self.session_factory() as session:
                env = db.load_environment(session, env_id)
            status = env.get("status") if env else None
            if status == EnvironmentStatus.READY:
                return env, None, False
            if status is None or (env and not isinstance(status, EnvironmentStatus)):
                return None, f"Invalid environment status: {status!r}", False

            return None, build.error_message or "Environment build failed", False
        finally:
            if got_lock:
                db.advisory_unlock(lock_conn, key=lock_key)
            lock_conn.close()

    def process_run(self, claim: db.RunClaim) -> None:
        now = utcnow()
        run_id = claim.id

        workspace_id = None
        run_dir: Path | None = None
        try:
    
            with self.session_factory() as session:
                run = db.load_run(session, run_id)
            if not run:
                logger.error("run not found: %s", run_id)
                return
    
            run_started_at = run.get("started_at") if isinstance(run.get("started_at"), datetime) else now
    
            workspace_id = str(run["workspace_id"])
            configuration_id = str(run["configuration_id"])
            input_file_version_id = str(run["input_file_version_id"])
            document_id = input_file_version_id
    
            ctx = {
                "job_id": run_id,
                "workspace_id": workspace_id,
                "configuration_id": configuration_id,
                "environment_id": None,
            }
    
            event_log = EventLog(self.paths.run_event_log_path(workspace_id, run_id))
    
            env, env_error, lost_claim = self._ensure_environment_ready(
                run=run,
                run_claim=claim,
                now=now,
            )
            if lost_claim:
                event_log.emit(
                    event="run.lost_claim",
                    level="warning",
                    message="Lease expired during environment build",
                    context=ctx,
                )
                return
            if not env:
                self._handle_run_failure(
                    claim,
                    run_id,
                    document_id,
                    event_log,
                    ctx,
                    now,
                    run_started_at,
                    2,
                    env_error or "Environment not ready",
                )
                return
    
            environment_id = str(env["id"])
            deps_digest = str(env["deps_digest"])
            ctx["environment_id"] = environment_id
    
            event_log.emit(event="run.start", message="Starting run", context=ctx)
    
            venv_dir = self.paths.environment_venv_dir(
                workspace_id,
                configuration_id,
                deps_digest,
                environment_id,
            )
            python_bin = self.paths.python_in_venv(venv_dir)
            if not python_bin.exists():
                logger.warning("environment python missing: %s", python_bin)
                with session_scope(self.session_factory) as session:
                    db.mark_environment_queued(
                        session,
                        env_id=environment_id,
                        now=now,
                        error_message="Missing venv python; requeueing environment",
                    )
                self._handle_run_failure(
                    claim,
                    run_id,
                    document_id,
                    event_log,
                    ctx,
                    now,
                    run_started_at,
                    2,
                    "Environment missing on disk",
                )
                return
    
            config_dir = self.paths.config_package_dir(workspace_id, configuration_id)
            if not config_dir.exists():
                self._handle_run_failure(
                    claim,
                    run_id,
                    document_id,
                    event_log,
                    ctx,
                    now,
                    run_started_at,
                    2,
                    f"Missing config package dir: {config_dir}",
                )
                return
    
            with session_scope(self.session_factory) as session:
                db.touch_environment_last_used(session, env_id=environment_id, now=now)
    
            options = parse_run_options(
                run.get("run_options"),
                default_log_level=self.settings.effective_worker_log_level,
            )
            sheet_names = options.input_sheet_names or _parse_input_sheet_names(run.get("input_sheet_names"))
            run_dir = self.paths.run_dir(workspace_id, run_id)
            _ensure_dir(run_dir)
    
            if options.dry_run:
                finished_at = utcnow()
                with session_scope(self.session_factory) as session:
                    ok = db.ack_run_success(
                        session,
                        run_id=run_id,
                        worker_id=self.worker_id,
                        now=finished_at,
                    )
                    if not ok:
                        event_log.emit(
                            event="run.lost_claim",
                            level="warning",
                            message="Lost run claim before ack",
                            context=ctx,
                        )
                        return
                    db.record_run_result(
                        session,
                        run_id=run_id,
                        completed_at=finished_at,
                        exit_code=0,
                        output_file_version_id=None,
                        error_message="Dry run",
                    )
                _emit_run_complete(
                    event_log,
                    status="succeeded",
                    message="Dry run complete",
                    context=ctx,
                    started_at=run_started_at,
                    completed_at=finished_at,
                    exit_code=0,
                )
                self._upload_run_log(workspace_id=workspace_id, run_id=run_id)
                return
    
            if options.validate_only:
                cmd = engine_config_validate_cmd(
                    python_bin=python_bin,
                    config_dir=config_dir,
                    log_level=options.log_level,
                )
                try:
                    res = self.runner.run(
                        cmd,
                        event_log=event_log,
                        scope="run.validate",
                        timeout_seconds=float(self.settings.worker_run_timeout_seconds)
                        if self.settings.worker_run_timeout_seconds
                        else None,
                        cwd=None,
                        env=self._pip_env(),
                        heartbeat=lambda: self._heartbeat_run(run_id=claim.id),
                        heartbeat_interval=max(1.0, self.settings.worker_lease_seconds / 3),
                        context=ctx,
                    )
                except HeartbeatLostError:
                    event_log.emit(
                        event="run.lost_claim",
                        level="warning",
                        message="Lease expired during validation",
                        context=ctx,
                    )
                    return
                finished_at = utcnow()
                if res.exit_code == 0:
                    with session_scope(self.session_factory) as session:
                        ok = db.ack_run_success(
                            session,
                            run_id=run_id,
                            worker_id=self.worker_id,
                            now=finished_at,
                        )
                        if not ok:
                            event_log.emit(
                                event="run.lost_claim",
                                level="warning",
                                message="Lost run claim before ack",
                                context=ctx,
                            )
                            return
                        db.record_run_result(
                            session,
                            run_id=run_id,
                            completed_at=finished_at,
                            exit_code=0,
                            output_file_version_id=None,
                            error_message=None,
                        )
                    _emit_run_complete(
                        event_log,
                        status="succeeded",
                        message="Validation succeeded",
                        context=ctx,
                        started_at=run_started_at,
                        completed_at=finished_at,
                        exit_code=0,
                    )
                    self._upload_run_log(workspace_id=workspace_id, run_id=run_id)
                else:
                    self._handle_run_failure(
                        claim,
                        run_id,
                        document_id,
                        event_log,
                        ctx,
                        finished_at,
                        run_started_at,
                        res.exit_code,
                        f"Validation failed (exit {res.exit_code})",
                    )
                return
    
            with self.session_factory() as session:
                file_version = db.load_file_version(session, input_file_version_id)
                if not file_version:
                    self._handle_run_failure(
                        claim,
                        run_id,
                        document_id,
                        event_log,
                        ctx,
                        now,
                        run_started_at,
                        2,
                        f"Document version not found: {input_file_version_id}",
                    )
                    return

                file_id = str(file_version.get("file_id") or "")
                document_id = file_id or document_id
                file_row = db.load_file(session, file_id)
            if not file_row:
                self._handle_run_failure(
                    claim,
                    run_id,
                    document_id,
                    event_log,
                    ctx,
                    now,
                    run_started_at,
                    2,
                    f"Document not found: {document_id}",
                )
                return
            kind = file_row.get("kind")
            if kind is None or not isinstance(kind, FileKind):
                self._handle_run_failure(
                    claim,
                    run_id,
                    document_id,
                    event_log,
                    ctx,
                    now,
                    run_started_at,
                    2,
                    f"Invalid document kind: {kind!r}",
                )
                return
            if kind != FileKind.INPUT:
                self._handle_run_failure(
                    claim,
                    run_id,
                    document_id,
                    event_log,
                    ctx,
                    now,
                    run_started_at,
                    2,
                    f"Document not found: {document_id}",
                )
                return
            if file_row.get("deleted_at") is not None:
                self._handle_run_failure(
                    claim,
                    run_id,
                    document_id,
                    event_log,
                    ctx,
                    now,
                    run_started_at,
                    2,
                    f"Document deleted: {document_id}",
                )
                return
    
            input_dir = self.paths.run_input_dir(workspace_id, run_id)
            output_dir = self.paths.run_output_dir(workspace_id, run_id)
            _ensure_dir(input_dir)
            _ensure_dir(output_dir)
    
            original_name = Path(
                str(file_version.get("filename_at_upload") or file_row.get("name") or "input")
            ).name
            staged_input = input_dir / original_name
            try:
                self.storage.download_to_path(
                    str(file_row.get("blob_name") or ""),
                    version_id=file_version.get("storage_version_id"),
                    destination=staged_input,
                )
            except FileNotFoundError:
                self._handle_run_failure(
                    claim,
                    run_id,
                    document_id,
                    event_log,
                    ctx,
                    now,
                    run_started_at,
                    2,
                    f"Document file missing: {file_row.get('blob_name')}",
                )
                return
            except Exception as exc:
                self._handle_run_failure(
                    claim,
                    run_id,
                    document_id,
                    event_log,
                    ctx,
                    now,
                    run_started_at,
                    2,
                    f"Document download failed: {exc}",
                )
                return
    
            engine_payload: dict[str, Any] | None = None
    
            def on_event(rec: dict[str, Any]) -> None:
                nonlocal engine_payload
                if rec.get("event") == "engine.run.completed":
                    data = rec.get("data")
                    if isinstance(data, dict):
                        engine_payload = data
    
            cmd = engine_process_file_cmd(
                python_bin=python_bin,
                input_path=staged_input,
                output_dir=output_dir,
                config_dir=config_dir,
                options=options,
                sheet_names=sheet_names,
            )

            try:
                res = self.runner.run(
                    cmd,
                    event_log=event_log,
                    scope="run.engine",
                    timeout_seconds=float(self.settings.worker_run_timeout_seconds)
                    if self.settings.worker_run_timeout_seconds
                    else None,
                    cwd=None,
                    env=self._pip_env(),
                    heartbeat=lambda: self._heartbeat_run(run_id=claim.id),
                    heartbeat_interval=max(1.0, self.settings.worker_lease_seconds / 3),
                    context=ctx,
                    on_json_event=on_event,
                )
            except HeartbeatLostError:
                event_log.emit(
                    event="run.lost_claim",
                    level="warning",
                    message="Lease expired during engine run",
                    context=ctx,
                )
                return

            finished_at = utcnow()
    
            if res.timed_out:
                self._handle_run_failure(
                    claim,
                    run_id,
                    document_id,
                    event_log,
                    ctx,
                    finished_at,
                    run_started_at,
                    res.exit_code,
                    "Run timed out",
                )
                return
    
            if res.exit_code == 0:
                output_path = _normalize_output_path(
                    _extract_output_path(engine_payload),
                    run_dir=run_dir,
                )
                if not output_path:
                    output_path = _infer_output_path(output_dir, run_dir=run_dir)
                results_payload = engine_payload if isinstance(engine_payload, dict) else None
                metrics = parse_run_metrics(results_payload) if results_payload else None
                fields = parse_run_fields(results_payload) if results_payload else []
                columns = parse_run_table_columns(results_payload) if results_payload else []
                output_file_row: dict[str, Any] | None = None
                output_upload: Any | None = None
                output_filename: str | None = None
    
                if output_path:
                    output_abs = (run_dir / output_path).resolve()
                    if output_abs.is_file():
                        output_filename = output_abs.name
                        output_display_name = f"{file_row.get('name') or output_filename} (Output)"
                        output_name_key = f"output:{file_id}"
                        with session_scope(self.session_factory) as session:
                            output_file_row = db.ensure_output_file(
                                session,
                                workspace_id=workspace_id,
                                source_file_id=file_id,
                                name=output_display_name,
                                name_key=output_name_key,
                                now=finished_at,
                            )
                        try:
                            output_upload = self.storage.upload_path(
                                str(output_file_row.get("blob_name") or ""),
                                output_abs,
                            )
                        except Exception as exc:
                            self._handle_run_failure(
                                claim,
                                run_id,
                                document_id,
                                event_log,
                                ctx,
                                finished_at,
                                run_started_at,
                                res.exit_code or 2,
                                f"Output upload failed: {exc}",
                            )
                            return
                    else:
                        output_path = None
                with session_scope(self.session_factory) as session:
                    ok = db.ack_run_success(
                        session,
                        run_id=run_id,
                        worker_id=self.worker_id,
                        now=finished_at,
                    )
                    if not ok:
                        event_log.emit(event="run.lost_claim", level="warning", message="Lost run claim before ack", context=ctx)
                        return
    
                    output_file_version_id: str | None = None
                    if output_upload and output_file_row:
                        storage_version_id = output_upload.version_id
                        content_type = None
                        if output_filename:
                            content_type = mimetypes.guess_type(output_filename)[0]
                        version_payload = db.create_output_file_version(
                            session,
                            file_id=str(output_file_row["id"]),
                            run_id=run_id,
                            filename_at_upload=output_filename or "output",
                            content_type=content_type,
                            sha256=output_upload.sha256,
                            byte_size=output_upload.byte_size,
                            storage_version_id=storage_version_id,
                            now=finished_at,
                        )
                        output_file_version_id = str(version_payload["id"])
    
                    db.record_run_result(
                        session,
                        run_id=run_id,
                        completed_at=finished_at,
                        exit_code=0,
                        output_file_version_id=output_file_version_id,
                        error_message=None,
                    )
    
                    if results_payload is None:
                        logger.warning("run.results.missing_payload run_id=%s", run_id)
                    else:
                        try:
                            with session.begin_nested():
                                db.replace_run_metrics(
                                    session,
                                    run_id=run_id,
                                    metrics=metrics,
                                )
                                db.replace_run_fields(
                                    session,
                                    run_id=run_id,
                                    rows=fields,
                                )
                                db.replace_run_table_columns(
                                    session,
                                    run_id=run_id,
                                    rows=columns,
                                )
                        except Exception:
                            logger.exception("run.results.persist_failed run_id=%s", run_id)
    
                _emit_run_complete(
                    event_log,
                    status="succeeded",
                    message="Run succeeded",
                    context=ctx,
                    started_at=run_started_at,
                    completed_at=finished_at,
                    exit_code=0,
                )
                self._upload_run_log(workspace_id=workspace_id, run_id=run_id)
                return
    
            self._handle_run_failure(
                claim,
                run_id,
                document_id,
                event_log,
                ctx,
                finished_at,
                run_started_at,
                res.exit_code,
                f"Engine failed (exit {res.exit_code})",
            )
    
        finally:
            if run_dir and workspace_id:
                self._cleanup_run_dir(run_dir=run_dir, workspace_id=workspace_id, run_id=run_id)

    def _handle_run_failure(
        self,
        claim: db.RunClaim,
        run_id: str,
        document_id: str,
        event_log: EventLog,
        ctx: dict[str, Any],
        now: datetime,
        started_at: datetime,
        exit_code: int,
        error_message: str,
    ) -> None:
        retry_at = self._retry_at(claim, now)

        with session_scope(self.session_factory) as session:
            ok = db.ack_run_failure(
                session,
                run_id=run_id,
                worker_id=self.worker_id,
                now=now,
                error_message=error_message,
                retry_at=retry_at,
            )
            if not ok:
                event_log.emit(event="run.lost_claim", level="warning", message="Lost run claim before ack", context=ctx)
                return

            if retry_at is None:
                db.record_run_result(
                    session,
                    run_id=run_id,
                    completed_at=now,
                    exit_code=exit_code,
                    output_file_version_id=None,
                    error_message=error_message,
                )
            else:
                db.record_run_result(
                    session,
                    run_id=run_id,
                    completed_at=None,
                    exit_code=None,
                    output_file_version_id=None,
                    error_message=error_message,
                )

        if retry_at is not None:
            event_log.emit(
                event="run.retry",
                level="error",
                message=f"Retry scheduled at {retry_at.isoformat()}",
                data={
                    "error_message": error_message,
                    "retry_at": retry_at.isoformat(),
                    "exit_code": exit_code,
                },
                context=ctx,
            )
            workspace_id = str(ctx.get("workspace_id") or "")
            if workspace_id:
                self._upload_run_log(workspace_id=workspace_id, run_id=run_id)
            return

        _emit_run_complete(
            event_log,
            status="failed",
            message=error_message,
            context=ctx,
            started_at=started_at,
            completed_at=now,
            exit_code=exit_code,
            error_message=error_message,
        )
        workspace_id = str(ctx.get("workspace_id") or "")
        if workspace_id:
            self._upload_run_log(workspace_id=workspace_id, run_id=run_id)

    def start(self) -> None:
        logger.info(
            "ade-worker starting worker_id=%s concurrency=%s",
            self.worker_id,
            self.settings.worker_concurrency,
        )

        max_workers = int(self.settings.worker_concurrency)
        listen_timeout = float(self.settings.worker_listen_timeout_seconds)
        maintenance_interval = float(self.settings.worker_cleanup_interval)
        next_maintenance = time.monotonic() + maintenance_interval

        listener = PgListener(self.settings, channel=CHANNEL_RUN_QUEUED)

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures: set[Future[None]] = set()
                startup_now = utcnow()
                self._drain(executor=executor, futures=futures, now=startup_now)

                while True:
                    self._reap(futures=futures)

                    now = utcnow()
                    mono = time.monotonic()

                    if mono >= next_maintenance:
                        try:
                            with session_scope(self.session_factory) as session:
                                expired_runs = int(
                                    db.expire_run_leases(
                                        session,
                                        now=now,
                                        backoff_base_seconds=int(self.settings.worker_backoff_base_seconds),
                                        backoff_max_seconds=int(self.settings.worker_backoff_max_seconds),
                                    )
                                )
                            if expired_runs:
                                logger.info("expired %s stuck run leases", expired_runs)
                        except Exception:
                            logger.exception("run lease expiration failed")
                        next_maintenance = mono + maintenance_interval

                    capacity = max_workers - len(futures)
                    if capacity > 0:
                        claimed = self._drain(executor=executor, futures=futures, now=now)
                        if claimed:
                            logger.info("run.queue.claimed count=%s", claimed)
                            continue

                    wait_seconds = max(0.0, min(listen_timeout, next_maintenance - mono))

                    with self.session_factory() as session:
                        next_due = db.next_run_due_at(session, now=now)
                    if next_due is not None:
                        if next_due.tzinfo is None:
                            next_due = next_due.replace(tzinfo=timezone.utc)
                        wait_seconds = min(wait_seconds, max(0.0, (next_due - now).total_seconds()))

                    if capacity <= 0 and futures:
                        if wait_seconds > 0:
                            wait(futures, timeout=wait_seconds, return_when=FIRST_COMPLETED)
                        continue

                    if wait_seconds <= 0:
                        continue

                    notified = listener.wait(wait_seconds)
                    if notified:
                        logger.info("run.queue.wake notify=true")
                        if NOTIFY_JITTER_MS > 0:
                            time.sleep(random.random() * (NOTIFY_JITTER_MS / 1000.0))
                    else:
                        logger.debug("run.queue.wake notify=false")
        finally:
            listener.close()

    def _submit(
        self,
        *,
        executor: ThreadPoolExecutor,
        futures: set[Future[None]],
        fn,
        claim: db.RunClaim,
    ) -> None:
        future = executor.submit(fn, claim)
        futures.add(future)

    def _reap(self, *, futures: set[Future[None]]) -> None:
        done = {f for f in futures if f.done()}
        for f in done:
            futures.remove(f)
            try:
                f.result()
            except Exception:
                logger.exception("work item crashed")

    def _drain(
        self,
        *,
        executor: ThreadPoolExecutor,
        futures: set[Future[None]],
        now: datetime,
    ) -> int:
        claimed_total = 0
        capacity = max(0, int(self.settings.worker_concurrency) - len(futures))
        if capacity <= 0:
            return 0

        while capacity > 0:
            batch_size = min(CLAIM_BATCH_SIZE, capacity)
            with session_scope(self.session_factory) as session:
                run_claims = db.claim_runs(
                    session,
                    worker_id=self.worker_id,
                    now=now,
                    lease_seconds=int(self.settings.worker_lease_seconds),
                    limit=batch_size,
                )
            if not run_claims:
                break
            for claim in run_claims:
                claimed_total += 1
                capacity -= 1
                self._submit(
                    executor=executor,
                    futures=futures,
                    fn=self.process_run,
                    claim=claim,
                )

        return claimed_total


# --- Main entrypoint ---

def main() -> int:
    settings = get_settings()
    _setup_logging(
        settings.effective_worker_log_level,
        log_format=settings.log_format,
    )

    _ensure_runtime_dirs(settings)

    engine = build_engine(settings)
    assert_tables_exist(engine, REQUIRED_TABLES)

    worker_id = settings.worker_id or _default_worker_id()

    paths = PathManager(settings, settings.pip_cache_dir)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    storage = build_storage_adapter(settings)

    runner = SubprocessRunner()

    Worker(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        worker_id=worker_id,
        paths=paths,
        runner=runner,
        storage=storage,
    ).start()
    return 0


def _run_capture_text(cmd: list[str]) -> str:
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    return out or err


__all__ = [
    "RunOptions",
    "parse_run_options",
    "parse_run_metrics",
    "parse_run_fields",
    "parse_run_table_columns",
    "EventLog",
    "HeartbeatLostError",
    "SubprocessRunner",
    "Worker",
    "main",
]
