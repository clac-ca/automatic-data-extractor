## Updated Work Package – ADE API Logging (Console Format)

> **Agent instruction (read first):**
>
> * Treat this work package as the **single source of truth** for ADE API logging.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [ ] Define ADE API logging guidelines (levels, logger naming, message style, `extra` field conventions, correlation ID). — guidelines not yet documented.
* [x] Implement console-style logging configuration (single root handler, consistent formatter, third‑party logger propagation). — `shared/core/logging.py` now uses `ConsoleLogFormatter` and propagates uvicorn/alembic/sqlalchemy; startup log now includes logging_level to verify env.
* [x] Add shared helpers (`bind_request_context`, `clear_request_context`, `log_context`) and adopt them in middleware/exception handlers. — middleware + new `shared/core/exceptions.py` now use `log_context` and correlation context.
* [x] Instrument critical services/routes (auth, workspaces, configurations/builds, runs, documents) with DEBUG/INFO/ERROR logs using the new pattern. — services + runs/builds routers now use `log_context`/event-style messages.
* [ ] Cover background/async pipelines (builders, run supervisor/streaming, background tasks) with failure/success logging. — supervisor now logs start/end/errors with `log_context`; runner warning updated; builder pipeline still only emits events via service.
* [x] Verify exception handling and logging behavior with smoke tests (5xx responses emit error logs with stack traces; request logs include correlation IDs and domain IDs where available). — added request/exception log capture tests (`apps/ade-api/tests/unit/shared/test_logging_behavior.py`).
* [x] Document the logging guidelines in `apps/ade-api/README.md` or `apps/ade-api/LOGGING.md`. — added logging section with format, `ADE_LOGGING_LEVEL`, and usage (`apps/ade-api/README.md`).

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.
> `- [x] Implemented console formatter and root config — {{commit_ref}}`

---

# ADE API Logging (Console, Structured)

## 1. Objective

**Goal**

Establish a consistent, standard Python logging approach across the ADE API (FastAPI backend) using **console‑style logs**, so that:

* server errors always surface in logs with stack traces,
* operational actions have traceable context (workspace/config/run/build/user IDs),
* developers know exactly how to log in a uniform way.

This work package is **only** about backend API logging. ADE Engine telemetry (`AdeEvent` ndjson) is separate; we only align on identifiers (`workspace_id`, `configuration_id`, `run_id`, `build_id`) to make cross‑correlation easier.

You will:

* Define API logging conventions (severity levels, logger names, correlation ID usage, `extra` fields).
* Configure a single root logger with a console formatter and propagate third‑party loggers.
* Add small utilities so structured logging is easy and frictionless.
* Instrument critical API paths and async pipelines so that failures and major lifecycle transitions are visible in logs.

The outcome should be:

* **Single‑line console logs** to stdout, with the shape:

  ```text
  2025-11-27T03:05:00.302Z INFO  ade_api.main [cid=abcd1234] run.create.success workspace_id=... configuration_id=... run_id=...
  ```

  where:

  * timestamp is UTC, ISO‑like with milliseconds and `Z`,
  * `level` is one of DEBUG/INFO/WARNING/ERROR/CRITICAL,
  * `logger` is the module name (e.g. `ade_api.features.runs.service`),
  * `[cid=...]` is the request correlation ID (or `-` if not set),
  * `message` is a short event‑style string,
  * trailing `key=value` pairs come from `extra` and carry domain context.

* A clear guarantee that:

  * any unexpected exception returning a 5xx is logged once with a stack trace, and
  * any deliberate 5xx (`HTTPException` with `status_code >= 500`) is also logged at ERROR.

* INFO/DEBUG‑level breadcrumbs for major lifecycle steps (auth, workspace/config changes, build/run start/end, document operations).

---

## 2. Context (current state)

Current ADE API logging behavior:

* **Root logging configuration**

  * `apps/ade-api/src/ade_api/shared/core/logging.py` currently configures the root logger with a JSON formatter and a single `StreamHandler`, with level from `Settings.logging_level` (`ADE_LOGGING_LEVEL`).
  * Uvicorn loggers are configured to propagate into the same root logger.

* **Request logging and correlation ID**

  * `RequestContextMiddleware` in `shared/core/middleware.py`:

    * Reads `X-Request-ID` header (or generates a UUID) and stores it on `request.state.correlation_id`.
    * Binds the correlation ID to a `ContextVar` so logs inside the request share the same `correlation_id`.
    * Emits an `ade_api.request` log for each request:

      * `request.complete` (INFO) with `path`, `method`, `duration_ms`, `status_code`.
      * `request.error` (ERROR) with the same fields; stack traces are handled by global exception handlers.

* **Global exception handlers**

  * `shared/core/exceptions.py`:

    * `unhandled_exception_handler` for uncaught exceptions, logs with stack trace and returns a 500 JSON error.
    * `http_exception_handler` for `HTTPException`, logging 5xx responses at ERROR while preserving the standard FastAPI response shape.
  * Handlers are registered in `main.py` so that unexpected exceptions and 5xx `HTTPException`s are always logged.

* **Existing log usage**

  * Runs: warnings and exceptions for manifest/summary failures and missing runs during streaming.
  * Builds: logs around background task failures; some services define a `logger` but rarely log lifecycle events.
  * Documents: warnings on fallbacks (e.g. cached worksheet metadata).
  * Auth: INFO/WARNING/ERROR around SSO provisioning and conflicts.
  * Many services/routes have little or no lifecycle logging; some background tasks and streaming flows can fail after the response is sent and currently only log if they raise all the way out.

* **Telemetry events**

  * The ADE Engine emits `AdeEvent` ndjson telemetry for runs. API logging is independent of this system, but logs can include the same IDs to make it easy to correlate API activity with engine telemetry if needed.

* **Inconsistencies**

  * No agreed standard for `extra` keys; some logs are descriptive strings instead of structured fields, leading to uneven output.
  * No explicit policy for what is safe to log (PII/secrets); some auth logs may log emails or other sensitive fields more than necessary.

---

## 3. Target architecture (ideal behavior)

We want API logging that is idiomatic for:

* Python’s built‑in `logging` module,
* FastAPI’s middleware/exception patterns,
* containerized deployments that read logs from stdout and forward them to log aggregators.

Target characteristics:

* **Single logging configuration** at startup:

  * Root logger configured once via `setup_logging(settings)`.
  * Per‑module loggers created with `logging.getLogger(__name__)`.
  * A single console `StreamHandler` with a uniform formatter.

* **Correlation and context**

  * Request‑scoped `correlation_id` is attached to all log records originating from that request (via the existing `ContextVar` and formatter).
  * Call sites log domain context explicitly through `extra=log_context(...)`:

    * canonical keys: `workspace_id`, `configuration_id`, `run_id`, `build_id`, `document_id`, `user_id`.
  * Additional metadata (e.g. `path`, `method`, `duration_ms`, `status_code`) are also provided via `extra`.

* **Severity and usage**

  * `DEBUG`: detailed diagnostics (key decisions, IDs, branches, control flow).
  * `INFO`: lifecycle events (auth/login, workspace/config create/update, build/run start/finish, document actions).
  * `WARNING`: recoverable anomalies and fallbacks.
  * `ERROR`: failures that cause an operation to fail (5xx responses, background task failures).
  * `CRITICAL`: system‑wide failures (e.g. startup blockers).

* **Exception handling**

  * Global `Exception` handler logs unexpected errors with `logger.exception` (stack traces) and returns a generic 500.
  * `HTTPException` handler logs any 5xx `HTTPException` at ERROR while preserving the response structure.
  * Coding rule: if you catch an exception and return a 5xx, log at ERROR/EXCEPTION before raising or re‑raising.

* **Redaction and PII**

  * Policy: log IDs and small metadata; avoid bodies and secrets.
  * Prefer `user_id` / `principal_id`; log email only when necessary (ideally at DEBUG).
  * Never log passwords, tokens, auth headers, or entire auth request bodies.

* **Project structure (unchanged)**

  ```text
  automatic-data-extractor/
    apps/ade-api/src/ade_api/
      main.py
      shared/core/{logging.py,middleware.py,exceptions.py}
      shared/{dependency.py,pagination.py,sorting.py,...}
      features/
        auth/
        workspaces/
        configs/
        builds/
        runs/
        documents/
        roles/
        system_settings/
      web/...
    apps/ade-api/tests/...
  ```

---

## 4. Logging methodology (how to log)

### 4.1 Configuration

* Logging is configured once per process via `setup_logging(settings)` in `shared/core/logging.py`, called from `create_app` in `main.py`.
* `ADE_LOGGING_LEVEL` (via `Settings.logging_level`) controls the root log level.
* A single `StreamHandler` with `ConsoleLogFormatter` is attached to the root logger.
* Common third‑party loggers (`uvicorn`, `uvicorn.error`, `uvicorn.access`, `alembic`, `sqlalchemy`) have their handlers cleared and `propagate=True`, so their logs adopt the same console format.

### 4.2 Format

Each log line (in the worker process) looks like:

```text
2025-11-27T03:05:00.302Z INFO  ade_api.features.runs.service [cid=abcd1234] run.create.success workspace_id=ws_123 configuration_id=cfg_456 run_id=run_789 user_id=user_1
```

* `timestamp`: UTC ISO‑style date/time with milliseconds and `Z`.
* `level`: padded to 5 characters (e.g. `INFO `, `ERROR`).
* `logger`: module or subsystem name (`__name__`).
* `[cid=...]`: request correlation ID (or `-` if not available).
* `message`: short, event‑style string (e.g. `run.create.start`, `auth.login.failed`).
* `key=value` pairs: any additional `extra` fields.

### 4.3 How to log in code

In any module:

```python
import logging
from ade_api.shared.core.logging import log_context

logger = logging.getLogger(__name__)

def example(workspace_id: str, configuration_id: str) -> None:
    logger.debug(
        "config.create.start",
        extra=log_context(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        ),
    )
    # ...
    logger.info(
        "config.create.success",
        extra=log_context(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
        ),
    )
```

Guidelines:

* Use **short, event‑style messages** (no long sentences).
* Attach IDs and relevant metadata via `extra=log_context(...)`.
* Let the formatter handle correlation IDs; do **not** duplicate them in `extra`.

### 4.4 Request and exception logs

* `RequestContextMiddleware`:

  * binds a correlation ID for each request.
  * logs an `ade_api.request` entry:

    ```text
    2025-11-27T03:10:00.100Z INFO  ade_api.request [cid=abcd1234] request.complete path=/api/v1/... method=POST status_code=201 duration_ms=23.7
    ```

* `unhandled_exception_handler`:

  * logs an ERROR with stack trace and context:

    ```text
    2025-11-27T03:10:00.200Z ERROR ade_api.errors [cid=abcd1234] unhandled_exception path=/api/v1/... method=POST exception_type=ValueError detail=...
    ```

* `http_exception_handler`:

  * logs 5xx `HTTPException`s at ERROR with status and detail.

---

## 5. Implementation notes

* **Coding standards**

  * Always use `logger = logging.getLogger(__name__)` in modules.
  * Always use `extra=log_context(...)` for domain IDs and metadata.
  * For unexpected exceptions you handle yourself, use `logger.exception(...)` before raising a 500.

* **Instrumentation targets**

  * Same as the previous work package (auth, workspaces/roles, configs/builds, runs, documents) but now using the console format and `log_context`.

* **Verification**

  * Start dev server with `ADE_LOGGING_LEVEL=DEBUG ade dev`.
  * Confirm:

    * Uvicorn worker + ADE + Alembic logs share the same console format.
    * Requests show `request.complete` / `request.error` lines with correlation IDs and durations.
    * 5xx responses (unexpected or HTTPException) generate ERROR logs with stack traces (for unexpected) or structured metadata (for explicit 5xx).

---

## Final scripts (new structure)

### 1. `apps/ade-api/src/ade_api/shared/core/logging.py`

```python
"""Logging configuration and helpers for the ADE API backend.

This module configures console-style logging for the entire process and exposes
helpers for:

* binding a request-scoped correlation ID, and
* building consistent `extra` payloads for structured logs.

Everything uses the standard :mod:`logging` library. The only customization is
the formatter, which renders one human-readable line per log record, including
timestamp, level, logger name, correlation ID, and any `extra` fields as
``key=value`` pairs.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from ade_api.settings import Settings

# ---------------------------------------------------------------------------
# Context and constants
# ---------------------------------------------------------------------------

# Request-scoped correlation ID, set/cleared by RequestContextMiddleware.
_CORRELATION_ID: ContextVar[str | None] = ContextVar(
    "api_app_correlation_id",
    default=None,
)

# Attributes that are already handled by logging and should not be copied into
# the extra key=value list.
_STANDARD_ATTRS: set[str] = {
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
    # We handle this explicitly in the base format.
    "correlation_id",
    # Uvicorn / asyncio add these; usually not useful in app logs.
    "taskName",
    "color_message",
}

_CONFIGURED_FLAG = "_ade_configured"


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


class ConsoleLogFormatter(logging.Formatter):
    """Render log records as single-line console output.

    Example line:

        2025-11-27T02:57:00.302Z INFO  ade_api.main [cid=1234abcd] ade_api.startup safe_mode=False auth_disabled=True
    """

    # ISO8601-ish UTC timestamp (seconds) – we'll append millis and 'Z'.
    _time_format = "%Y-%m-%dT%H:%M:%S"

    def __init__(self) -> None:
        # correlation_id will be injected into the record in format().
        fmt = "%(asctime)s %(levelname)-5s %(name)s [cid=%(correlation_id)s] %(message)s"
        super().__init__(fmt=fmt, datefmt=self._time_format)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=UTC)
        pattern = datefmt or self._time_format
        base = dt.strftime(pattern)
        # Attach milliseconds + Z suffix.
        return f"{base}.{int(record.msecs):03d}Z"

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - std signature
        # Ensure correlation_id is always present so the format string works.
        cid = getattr(record, "correlation_id", None) or _CORRELATION_ID.get() or "-"
        record.correlation_id = cid

        # Let the base Formatter build the core line.
        base = super().format(record)

        # Append any custom fields from `extra=...` as key=value pairs.
        extras: list[str] = []
        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key.startswith("_"):
                continue
            extras.append(f"{key}={_format_extra_value(value)}")

        if extras:
            return f"{base} " + " ".join(extras)
        return base


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def setup_logging(settings: Settings) -> None:
    """Configure root logging for the ADE API process.

    This installs a single console-style StreamHandler on stdout and sets the
    root log level from ``settings.logging_level`` (env: ``ADE_LOGGING_LEVEL``).

    It also wires common third-party loggers (uvicorn, alembic, sqlalchemy) to
    propagate into the same root logger so that all logs share a consistent
    format and configuration.
    """
    root_logger = logging.getLogger()

    level_name = settings.logging_level.upper()
    level = getattr(logging, level_name, logging.INFO)

    # Only fully configure once per process; subsequent calls just adjust level.
    if getattr(root_logger, _CONFIGURED_FLAG, False):
        root_logger.setLevel(level)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(ConsoleLogFormatter())

    # Replace any existing handlers to avoid duplicate logs.
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    # Let common third-party loggers propagate into our root logger.
    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "alembic",
        "alembic.runtime.migration",
        "sqlalchemy",
    ):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    setattr(root_logger, _CONFIGURED_FLAG, True)


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def bind_request_context(correlation_id: str | None) -> None:
    """Bind a correlation ID to the logging context for the current request."""
    _CORRELATION_ID.set(correlation_id)


def clear_request_context() -> None:
    """Clear the request-scoped logging context."""
    _CORRELATION_ID.set(None)


def log_context(
    *,
    workspace_id: str | None = None,
    configuration_id: str | None = None,
    run_id: str | None = None,
    build_id: str | None = None,
    document_id: str | None = None,
    user_id: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build a consistent `extra` payload for structured logs.

    Example:
        logger.info(
            "run.create.success",
            extra=log_context(
                workspace_id=ws_id,
                configuration_id=cfg_id,
                run_id=run_id,
                user_id=user.id,
            ),
        )
    """
    ctx: dict[str, Any] = {}

    if workspace_id is not None:
        ctx["workspace_id"] = workspace_id
    if configuration_id is not None:
        ctx["configuration_id"] = configuration_id
    if run_id is not None:
        ctx["run_id"] = run_id
    if build_id is not None:
        ctx["build_id"] = build_id
    if document_id is not None:
        ctx["document_id"] = document_id
    if user_id is not None:
        ctx["user_id"] = user_id

    # Allow arbitrary additional structured fields.
    for key, value in extra.items():
        ctx[key] = value

    return ctx


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_extra_value(value: Any) -> str:
    """Format an `extra` value for console output."""
    if isinstance(value, (int, float, bool)):
        return str(value)
    if value is None:
        return "null"
    return str(value)


__all__ = [
    "ConsoleLogFormatter",
    "bind_request_context",
    "clear_request_context",
    "log_context",
    "setup_logging",
]
```

---

### 2. `apps/ade-api/src/ade_api/shared/core/exceptions.py`

```python
"""Centralized FastAPI exception handlers with structured logging."""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from ade_api.shared.core.logging import log_context

_UNHANDLED_LOGGER = logging.getLogger("ade_api.errors")
_HTTP_LOGGER = logging.getLogger("ade_api.http")


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected exceptions.

    Registered as the ``Exception`` handler. Ensures that any unhandled error
    results in:

    * a JSON error response with HTTP 500, and
    * a structured ERROR log including a stack trace.
    """
    _UNHANDLED_LOGGER.exception(
        "unhandled_exception",
        extra=log_context(
            path=str(request.url.path),
            method=request.method,
            exception_type=type(exc).__name__,
            detail=str(exc),
        ),
    )

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handler for FastAPI HTTPException instances.

    4xx responses (client errors) are returned without logging by default.
    5xx responses are logged at ERROR level with structured metadata.
    """
    if exc.status_code >= 500:
        _HTTP_LOGGER.error(
            "http_exception",
            extra=log_context(
                path=str(request.url.path),
                method=request.method,
                status_code=exc.status_code,
                detail=exc.detail,
            ),
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


__all__ = [
    "http_exception_handler",
    "unhandled_exception_handler",
]
```

---

### 3. `apps/ade-api/src/ade_api/shared/core/middleware.py`

```python
"""Custom FastAPI middleware components."""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from ade_api.settings import get_settings
from .logging import bind_request_context, clear_request_context, log_context

_REQUEST_LOGGER = logging.getLogger("ade_api.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach correlation IDs and emit structured request logs."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        correlation_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.correlation_id = correlation_id
        bind_request_context(correlation_id)

        start = time.perf_counter()
        response: Response | None = None
        error: bool = False

        try:
            response = await call_next(request)
        except Exception:  # pragma: no cover - defensive logging path
            error = True
            # Stack trace will be logged by the global exception handler.
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0

            extra = log_context(
                path=request.url.path,
                method=request.method,
                duration_ms=round(duration_ms, 2),
                status_code=response.status_code if response is not None else None,
            )

            if not error and response is not None:
                _REQUEST_LOGGER.info("request.complete", extra=extra)
            else:
                _REQUEST_LOGGER.error("request.error", extra=extra)

            clear_request_context()

        if response is None:  # pragma: no cover - defensive guard
            raise RuntimeError("Request handler returned no response")

        response.headers["X-Request-ID"] = correlation_id
        return response


def register_middleware(app: FastAPI) -> None:
    """Register ADE default middleware on the FastAPI application."""

    settings = get_settings()

    origins = list(settings.server_cors_origins)
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(RequestContextMiddleware)


__all__ = ["RequestContextMiddleware", "register_middleware"]
```
