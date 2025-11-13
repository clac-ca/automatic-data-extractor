# ADE Runs API Spec

The ADE Runs API mirrors the shape of the OpenAI API for managing "ADE runs"—single executions of the ADE engine for a specific configuration. This document captures the core concepts, data models, schemas, service behaviors, and HTTP endpoints required to implement the feature in FastAPI using SQLAlchemy.

---

## 1. Core Concepts & Naming

**Primary resource:** `Run` — a persistent record representing one execution of ADE for a given config.

Supporting concepts:
- **Run status:** lifecycle state of a run (`queued`, `running`, `succeeded`, `failed`, `canceled`).
- **Run logs:** text/structured output captured during execution.
- **Run events:** streaming payloads emitted over HTTP when `stream: true` is requested.

Naming conventions:
- SQLAlchemy models / tables:
  - `Run` → table `runs`
  - `RunLog` → table `run_logs`
- Pydantic object types: `"ade.run"` and `"ade.run.event"`
- Enum: `RunStatus` with string values `"queued" | "running" | "succeeded" | "failed" | "canceled"`
- API endpoint base paths:
  - `POST /api/v1/configs/{config_id}/runs` — create a run, optionally stream execution
  - `GET /api/v1/runs/{run_id}` — retrieve run status snapshot
  - `GET /api/v1/runs/{run_id}/logs` — fetch run logs (paged/offset)

---

## 2. Database Models (SQLAlchemy)

Assume SQLAlchemy `Base` is already available within the FastAPI application.

### 2.1 Run Status Enum

```python
# apps/api/app/features/runs/models.py
import enum


class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
```

### 2.2 Run Model

```python
# apps/api/app/features/runs/models.py
from datetime import datetime
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from apps.api.app.db.base_class import Base  # adjust import to local Base
from .enums import RunStatus  # as defined above


class Run(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True, index=True)  # e.g. "run_abc123"
    config_id = Column(String, ForeignKey("configs.id"), nullable=False, index=True)

    status = Column(Enum(RunStatus), nullable=False, index=True, default=RunStatus.QUEUED)
    exit_code = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    logs = relationship("RunLog", back_populates="run", cascade="all, delete-orphan")
```

### 2.3 RunLog Model

```python
# apps/api/app/features/runs/models.py
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from apps.api.app.db.base_class import Base


class RunLog(Base):
    __tablename__ = "run_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    run_id = Column(String, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    stream = Column(String, nullable=False, default="stdout")
    message = Column(Text, nullable=False)

    run = relationship("Run", back_populates="logs")
```

---

## 3. Pydantic Schemas

Define response and request payloads to match OpenAI-style semantics while reflecting ADE-specific data.

### 3.1 Shared Types

```python
# apps/api/app/features/runs/schemas.py
from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

RunObjectType = Literal["ade.run"]
RunEventObjectType = Literal["ade.run.event"]
RunStatusLiteral = Literal["queued", "running", "succeeded", "failed", "canceled"]
```

### 3.2 Run (Read) Schema

```python
class Run(BaseModel):
    id: str
    object: RunObjectType = "ade.run"

    config_id: str
    status: RunStatusLiteral

    created: int = Field(..., description="Unix timestamp seconds when run was created")
    started: Optional[int] = Field(None, description="Unix timestamp seconds when run started")
    finished: Optional[int] = Field(None, description="Unix timestamp seconds when run finished")

    exit_code: Optional[int] = None
    summary: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        orm_mode = True
```

Convert database datetimes to epoch seconds (e.g., `int(dt.timestamp())`) within the service layer.

### 3.3 Run Create Request

```python
class RunCreateOptions(BaseModel):
    dry_run: bool = False
    validate_only: bool = False
    # extend with ADE-specific toggles as needed


class RunCreateRequest(BaseModel):
    stream: bool = False
    options: RunCreateOptions = Field(default_factory=RunCreateOptions)
```

### 3.4 Run Event Schemas (Streaming)

Streaming responses use NDJSON lines, e.g. `{"object":"ade.run.event","type":"run.created",...}`. Define event variants:

```python
class RunEventBase(BaseModel):
    object: RunEventObjectType = "ade.run.event"
    run_id: str
    created: int  # unix timestamp seconds
    type: str     # "run.created" | "run.started" | "run.log" | "run.completed" | ...


class RunCreatedEvent(RunEventBase):
    type: Literal["run.created"] = "run.created"
    status: RunStatusLiteral
    config_id: str


class RunStartedEvent(RunEventBase):
    type: Literal["run.started"] = "run.started"


class RunLogEvent(RunEventBase):
    type: Literal["run.log"] = "run.log"
    stream: Literal["stdout", "stderr"] = "stdout"
    message: str


class RunCompletedEvent(RunEventBase):
    type: Literal["run.completed"] = "run.completed"
    status: RunStatusLiteral
    exit_code: Optional[int] = None
    error_message: Optional[str] = None


RunEvent = RunCreatedEvent | RunStartedEvent | RunLogEvent | RunCompletedEvent
```

Streaming payloads should serialize as `json.dumps(event.dict()) + "\n"`.

---

## 4. Service Layer Sketch

Provide helpers to create runs, update status, append logs, and execute the ADE engine while optionally streaming events.

### 4.1 Service Utilities

```python
# apps/api/app/features/runs/service.py
import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .models import Run, RunLog, RunStatus
from .schemas import (
    Run as RunSchema,
    RunCreateRequest,
    RunCreatedEvent,
    RunStartedEvent,
    RunLogEvent,
    RunCompletedEvent,
)


async def create_run(db: AsyncSession, config_id: str) -> Run:
    run_id = f"run_{uuid.uuid4().hex}"
    now = datetime.utcnow()
    run = Run(
        id=run_id,
        config_id=config_id,
        status=RunStatus.QUEUED,
        created_at=now,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


def run_to_schema(run: Run) -> RunSchema:
    def ts(dt: Optional[datetime]) -> Optional[int]:
        return int(dt.timestamp()) if dt else None

    return RunSchema(
        id=run.id,
        config_id=run.config_id,
        status=run.status.value,
        created=ts(run.created_at) or 0,
        started=ts(run.started_at),
        finished=ts(run.finished_at),
        exit_code=run.exit_code,
        summary=run.summary,
        error_message=run.error_message,
    )


async def update_run_status(
    db: AsyncSession,
    run: Run,
    status: RunStatus,
    *,
    exit_code: Optional[int] = None,
    error_message: Optional[str] = None,
) -> Run:
    now = datetime.utcnow()
    if status == RunStatus.RUNNING:
        run.started_at = run.started_at or now
    if status in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED):
        run.finished_at = now

    run.status = status
    if exit_code is not None:
        run.exit_code = exit_code
    if error_message is not None:
        run.error_message = error_message

    await db.commit()
    await db.refresh(run)
    return run


async def append_run_log(db: AsyncSession, run_id: str, message: str, *, stream: str = "stdout") -> RunLog:
    log = RunLog(run_id=run_id, message=message, stream=stream)
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log
```

### 4.2 ADE Engine Runner with Streaming

```python
async def run_ade_engine_stream(
    db: AsyncSession,
    run: Run,
    *,
    venv_path: str,
    config_package: str,
    options: dict,
) -> AsyncIterator[RunCreatedEvent | RunStartedEvent | RunLogEvent | RunCompletedEvent]:
    now = datetime.utcnow()

    # Emit run.created event
    yield RunCreatedEvent(
        run_id=run.id,
        created=int(now.timestamp()),
        status=run.status.value,
        config_id=run.config_id,
    )

    # Transition to running
    run = await update_run_status(db, run, RunStatus.RUNNING)
    now = datetime.utcnow()
    yield RunStartedEvent(
        run_id=run.id,
        created=int(now.timestamp()),
    )

    python_executable = os.path.join(venv_path, "bin", "python")
    cmd = [
        python_executable,
        "-m",
        "ade_engine.run",
        "--config",
        config_package,
        # map options into CLI flags here as needed
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=build_venv_env(venv_path),
    )

    assert process.stdout is not None

    async for raw_line in process.stdout:
        text = raw_line.decode("utf-8", errors="replace").rstrip("\n")
        await append_run_log(db, run.id, message=text, stream="stdout")

        now = datetime.utcnow()
        yield RunLogEvent(
            run_id=run.id,
            created=int(now.timestamp()),
            stream="stdout",
            message=text,
        )

    return_code = await process.wait()
    status = RunStatus.SUCCEEDED if return_code == 0 else RunStatus.FAILED
    run = await update_run_status(
        db,
        run,
        status,
        exit_code=return_code,
        error_message=None if status == RunStatus.SUCCEEDED else "ADE run failed",
    )

    now = datetime.utcnow()
    yield RunCompletedEvent(
        run_id=run.id,
        created=int(now.timestamp()),
        status=run.status.value,
        exit_code=run.exit_code,
        error_message=run.error_message,
    )
```

> `build_venv_env` should construct the environment for the virtualenv-based subprocess (e.g., `PATH`, `VIRTUAL_ENV`).

For non-streaming runs, invoke the same function within a background task and ignore yielded events (they still update the database).

---

## 5. Router Endpoints & `stream` Flag

FastAPI endpoints mimic OpenAI’s dual response strategy: synchronous JSON for non-streaming runs, NDJSON event streams when `stream: true`.

### 5.1 `POST /api/v1/configs/{config_id}/runs`

```python
# apps/api/app/features/runs/router.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncIterator
import json

from .models import Run, RunLog
from .schemas import RunCreateRequest, Run as RunSchema
from .service import create_run, run_to_schema, run_ade_engine_stream
from apps.api.app.core.db import get_session

router = APIRouter(prefix="/api/v1", tags=["runs"])


@router.post(
    "/configs/{config_id}/runs",
    response_model=RunSchema,
    responses={200: {"description": "Non-streaming run"}},
)
async def create_run_endpoint(
    config_id: str,
    body: RunCreateRequest,
    db: AsyncSession = Depends(get_session),
):
    run = await create_run(db, config_id=config_id)

    if not body.stream:
        # Trigger background execution here (FastAPI BackgroundTasks, task queue, etc.)
        return run_to_schema(run)

    async def event_stream() -> AsyncIterator[bytes]:
        async for event in run_ade_engine_stream(
            db=db,
            run=run,
            venv_path=f"/path/to/venvs/{config_id}",  # resolve dynamically
            config_package="ade_config",              # derive actual package name
            options=body.options.dict(),
        ):
            yield (json.dumps(event.dict()) + "\n").encode("utf-8")

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
```

- `stream: false` → returns a `Run` object immediately and starts execution in the background.
- `stream: true` → streams `RunEvent` payloads: `run.created`, `run.started`, repeated `run.log`, and final `run.completed`.

### 5.2 `GET /api/v1/runs/{run_id}`

```python
@router.get("/runs/{run_id}", response_model=RunSchema)
async def get_run(run_id: str, db: AsyncSession = Depends(get_session)):
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_to_schema(run)
```

### 5.3 `GET /api/v1/runs/{run_id}/logs`

```python
from pydantic import BaseModel


class RunLogEntry(BaseModel):
    id: int
    created: int
    stream: str
    message: str

    class Config:
        orm_mode = True


class RunLogsResponse(BaseModel):
    run_id: str
    object: Literal["ade.run.logs"] = "ade.run.logs"
    entries: List[RunLogEntry]


@router.get("/runs/{run_id}/logs", response_model=RunLogsResponse)
async def get_run_logs(
    run_id: str,
    db: AsyncSession = Depends(get_session),
    after_id: int | None = None,
):
    q = db.query(RunLog).filter(RunLog.run_id == run_id)
    if after_id is not None:
        q = q.filter(RunLog.id > after_id)
    q = q.order_by(RunLog.id.asc()).limit(1000)
    rows = (await q).all()  # adjust for your async ORM usage

    entries = [
        RunLogEntry(
            id=row.id,
            created=int(row.created_at.timestamp()),
            stream=row.stream,
            message=row.message,
        )
        for row in rows
    ]

    return RunLogsResponse(run_id=run_id, entries=entries)
```

---

## 6. End-to-End Flow Summary

- **Run model:** persists status, timestamps, exit info, and a summary/error message. Exposed as `RunSchema` (`object: "ade.run"`).
- **RunLog model:** stores log chunks, available via `/runs/{id}/logs` or emitted through `run.log` streaming events.
- **`stream` flag behavior:**
  - `POST /configs/{config_id}/runs` with `{ "stream": false }` — create run, launch background execution, return snapshot.
  - `POST /configs/{config_id}/runs` with `{ "stream": true }` — create run, execute inline, stream NDJSON `RunEvent` payloads.
- **Frontend integration:**
  - Non-streaming: treat runs as jobs, poll `/runs/{id}` and `/runs/{id}/logs`.
  - Streaming: handle NDJSON like OpenAI, update UI incrementally.
- **Implementation checklist for agents:**
  - Alembic migration for `runs` and `run_logs` tables.
  - SQLAlchemy models matching the spec.
  - Pydantic schemas for runs, creation options, and events.
  - Service-layer helpers plus ADE engine runner.
  - Router endpoints implementing the described behavior.

This document serves as the implementation contract for ADE run execution APIs and will be used when building the job endpoint and ADE engine integrations.

---

## 7. Environment & Operational Notes

- **Safe mode (`ADE_SAFE_MODE`)** — when set to `true`, the API short-circuits run execution after emitting a `run.log` message and marks the run as succeeded with a "Safe mode skip" summary. Keep this enabled during incident response or while rolling out migrations.
- **Virtual environment layout** — the runner expects a Python executable at `<venv_path>/bin/python` (or `Scripts/python.exe` on Windows). `ConfigurationBuild.venv_path` should therefore point to the virtualenv root created by the build service.
- **Operations runbook** — consult `docs/admin-guide/runs_observability.md` for streaming/polling instructions and `docs/reference/runs_deployment.md` before promoting changes to staging or production.
- **Engine entry point** — the orchestration service invokes `python -m ade_engine`. The CLI lives in `packages/ade-engine/src/ade_engine/__main__.py` and prints engine metadata/manifest details, matching the expected entry point in this spec.

## 8. Manual QA Checklist

1. **Background execution** (`stream: false`)
   - Issue `POST /api/v1/configs/{config_id}/runs` with the default payload.
   - Confirm a `201` snapshot response.
   - Poll `GET /api/v1/runs/{run_id}` until the status transitions to `succeeded`.
   - Fetch logs via `GET /api/v1/runs/{run_id}/logs` and verify the `next_after_id` cursor when more than one page is returned.
2. **Streaming execution** (`stream: true`)
   - Call the same endpoint with `{ "stream": true }`.
   - Ensure the response is `application/x-ndjson` and emits `run.created`, `run.started`, zero-or-more `run.log`, and a terminal `run.completed` event.
   - Abort the client mid-stream and confirm the run finishes with status `canceled` and an error summary of "Run execution cancelled".
3. **Validate-only guardrails**
   - Send `{ "options": { "validate_only": true } }` and verify the run completes immediately with summary "Validation-only execution" and exit code `0`.
4. **Safe mode verification**
   - Toggle `ADE_SAFE_MODE=true` and repeat the streaming request; the event stream should contain a log message noting safe mode and finish with status `succeeded` without invoking the engine subprocess.

## 9. Follow-up Enhancements

- Persist streamed events to disk alongside database storage (e.g., append to `<run_id>/events.ndjson`) so downstream tooling can tail runs without hitting the API.
- Extend operational tooling (`npm run workpackage`, admin dashboards) with run visibility once the backend stabilises.
- Capture observability metrics (run durations, failure counts) and surface them via the existing monitoring stack.
