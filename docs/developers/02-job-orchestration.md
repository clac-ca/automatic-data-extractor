# 02 — Job Orchestration (Deep Dive)

This page explains **how ADE runs a job** from end to end—simply and safely—inside a **single Docker container**.  
No background is required: we’ll start with what a “job” is, then layer on the queue, the worker process, the
artifact JSON, and the API that ties it together. Each idea is shown first in plain language and then cemented
with a small code snippet.

---

## 1) What is a “job”?

A **job** is one run of ADE on one spreadsheet using one versioned configuration (your small Python rules).  
The job reads your file, applies your config across **passes** (find tables → map columns → transform → validate → write),
and writes two outputs into a per-job folder:

- `artifact.json` — a complete audit of decisions (no raw cell values)  
- `normalized.xlsx` — the clean, normalized workbook

We keep every job **isolated** in its own working directory under `/var/jobs/<id>/`.
> **Note:** The `/var` prefix assumes the default container layout. In local development the base path comes
> from `ADE_STORAGE_DATA_DIR` (default `data/`), so `/var/jobs/<id>/` becomes `<data>/jobs/<id>/` when you
> run ADE without Docker.

```text
/var/jobs/1234/
├─ inputs/
│  └─ 01-input.xlsx
├─ artifact.json
├─ normalized.xlsx
├─ events.ndjson          # structured lifecycle events (append-only)
├─ run-request.json       # JSON payload handed to the worker
└─ config/                 # the code you authored in the UI (materialized for this run)
   ├─ __init__.py
   ├─ row_types/  __init__.py  *.py
   ├─ columns/    __init__.py  *.py
   ├─ hooks/      __init__.py  *.py
   ├─ requirements.txt  (optional)
   └─ vendor/            # legacy fallback when activation metadata is missing
````

---

## 2) The one-sentence model

**ADE accepts jobs via HTTP, reserves queue capacity up front, and runs each job in a separate Python subprocess
with strict resource limits, an activation-time virtualenv, and no network by default.**

```python
# high level pseudocode (not production code)
reserve_slot()       # POST /jobs, 202 + Location header
enqueue(job_id)      # persisted after the reservation succeeds
--N workers-->       # bounded concurrency (single-process manager)
spawn subprocess     # one per job
  |-> set rlimits    # CPU, memory, file size, fds
  |-> use activation venv  # per-config Python with pip-installed deps
  |-> disable net    # unless runtime_network_access=true
  |-> run passes     # write artifact.json + normalized.xlsx + events.ndjson
```

---

## 3) The Job API (how clients interact)

Clients create, check, and retrieve jobs over simple HTTP endpoints.

```python
# app/routes/jobs.py  (sketch)
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

router = APIRouter()

class SubmitJob(BaseModel):
    config_version_id: str
    document_ids: list[str] = []
    runtime_network_access: bool = False

@router.post("/jobs", status_code=202)
async def submit_job(payload: SubmitJob, response: Response):
    # 1) refuse when queue/backlog is full (no DB row is created)
    reservation = app.state.job_manager.try_reserve()
    if reservation is None:
        raise HTTPException(
            status_code=429,
            detail={"message": "Queue saturated", "retry_after": app.state.job_manager.retry_after_hint()},
            headers={"Retry-After": str(app.state.job_manager.retry_after_hint())},
        )

    # 2) create the job row after the reservation succeeds
    job_id = await create_job_and_files(payload)

    # 3) enqueue (always async; inline execution path has been removed)
    await app.state.job_manager.enqueue(job_id, reservation)

    location = f"/api/v1/workspaces/{payload.workspace_id}/jobs/{job_id}"
    response.headers["Location"] = location
    return {"job_id": job_id, "status": "queued"}

@router.get("/jobs/{job_id}")
async def get_job(job_id: int):
    return await read_job_row(job_id)  # status, timestamps, error_message, etc.

@router.get("/jobs/{job_id}/artifact")
async def get_artifact(job_id: int):
    return file_response(f"/var/jobs/{job_id}/artifact.json")

@router.get("/jobs/{job_id}/output")
async def get_output(job_id: int):
    return file_response(f"/var/jobs/{job_id}/normalized.xlsx")

@router.post("/jobs/{job_id}/retry", status_code=202)
async def retry_job(job_id: int, response: Response):
    reservation = app.state.job_manager.try_reserve()
    if reservation is None:
        raise HTTPException(status_code=429, detail="Queue saturated")
    retry = await create_retry_attempt(job_id)
    await app.state.job_manager.enqueue(retry.job_id, reservation)
    response.headers["Location"] = f"/api/v1/workspaces/{retry.workspace_id}/jobs/{retry.job_id}"
    return {"job_id": retry.job_id, "status": "queued", "retry_of": job_id, "attempt": retry.attempt}
```

---

### Safe mode (`ADE_SAFE_MODE`)

When the environment variable `ADE_SAFE_MODE` is set to `true`, ADE enters a recovery mode that keeps the API and UI online while skipping any configuration execution. The behaviour changes are:

- Job submissions are rejected with HTTP 400 (`JobSubmissionError`) using the message “ADE_SAFE_MODE is enabled…”.
- The orchestrator refuses to spawn worker subprocesses, protecting future code paths that might bypass the service guard.
- `/api/v1/health` includes a `safe-mode` component with a `degraded` status so dashboards (and CI) can detect the state without special handling.
- The frontend surfaces a banner, disables the “Run extraction” buttons, and adds tooltips that point operators back to the `ADE_SAFE_MODE` toggle.
- Existing job artifacts remain readable; once the config package is fixed, restart ADE without the flag to resume normal processing.

Use safe mode as an escape hatch after deploying a broken config package—flip it on, revert the offending code, restart normally.

---

## 4) The queue (bounded work-in-progress)

ADE runs a **single-process** manager with a bounded queue. Every submission reserves capacity before we
touch the database, so if saturation happens we return **HTTP 429** without creating a job row. On
startup the manager rehydrates queued jobs from the database and reclaims stale “running” jobs that lack a
recent heartbeat.

```python
# app/jobs/manager.py  (sketch)
import os, asyncio, sys, datetime as dt

class JobManager:
    def __init__(self, max_workers: int, max_queue: int):
        self.queue = asyncio.Queue(maxsize=max_queue)
        self.max_workers = max_workers
        self._workers: list[asyncio.Task[None]] = []
        self._inflight: set[int] = set()

    async def start(self):
        for i in range(self.max_workers):
            self._workers.append(asyncio.create_task(self._loop(i)))

    def try_reserve(self) -> bool:
        if self.queue.full():
            return False
        self._inflight.add(object())  # placeholder handle
        return True

    async def enqueue(self, job_id: int):
        await self.queue.put(job_id)

    async def _loop(self, worker_id: int):
        while True:
            job_id = await self.queue.get()
            try:
                await self._process(job_id)
            finally:
                self.queue.task_done()

    async def _process(self, job_id: int):
        await db.mark_running(job_id)
        rc, error = await self._spawn(job_id)       # see next section
        await db.finish(job_id, success=(rc == 0), error_message=error)

# Startup hook (e.g., app lifespan)
job_manager = JobManager(
    max_workers=int(os.getenv("ADE_QUEUE_MAX_CONCURRENCY", "2")),
    max_queue=int(os.getenv("ADE_QUEUE_MAX_SIZE", "10")),
)
await job_manager.start()
app.state.job_manager = job_manager
```

---

## 5) Activation environment (per-version virtualenv)

Every config version owns a **dedicated virtual environment** that is built during activation, not at
job time. The activation pipeline runs in four ordered steps:

1. Detect `requirements.txt` inside the uploaded package.
2. Create `<ADE_ACTIVATION_ENVS_DIR>/<config_version_id>/` (default root `data/venvs/`).
3. Run `pip install -r requirements.txt` with non-interactive flags and capture `pip freeze` into
   `activation/packages.txt`.
4. Execute `hooks/on_activate/*.py` inside that venv; any failure leaves the version inactive and
   records diagnostics.

ADE persists the activation snapshot alongside the package under
`configs/<config_id>/<sequence>/activation/`:

```text
activation/
├─ result.json        # status, timestamps, interpreter path, diagnostics
├─ install.log        # stdout/stderr from pip install
├─ packages.txt       # frozen dependency list
└─ hooks.json         # annotations + diagnostics from on_activate hooks
```

When activation succeeds, job submissions launch the worker with the stored `python_executable`. If no
metadata exists (legacy packages), ADE falls back to the vendored code bundled inside the config.

---

## 6) Spawning the worker (the safety boundary)

Each job runs in **its own Python process**. That process sees only the standard library plus the job’s
`config/` and `config/vendor/` folders on `PYTHONPATH`. We skip global site‑packages and capture all output to `logs.txt`.

```python
# app/jobs/manager.py  (spawn sketch)
import asyncio, os, sys, pathlib

WORKER = "/app/app/jobs/worker.py"        # absolute path to our worker script

async def _spawn(self, job_id: int):
    job_dir = pathlib.Path(f"/var/jobs/{job_id}")
    events = job_dir / "events.ndjson"

    python_cmd = activation.python_executable or sys.executable
    pythonpath = f"{job_dir}/config"
    if activation.python_executable is None:
        # Legacy fallback: allow vendored deps when activation metadata is absent
        pythonpath = f"{job_dir}/config/vendor:{pythonpath}"

    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        # Only the job’s code (and legacy vendor fallback) are importable:
        "PYTHONPATH": pythonpath,
        # Controls:
        "ADE_RUNTIME_NETWORK_ACCESS_JOB": str(
            await db.get_runtime_network_access(job_id)
        ).lower(),
        "ADE_WHEELHOUSE": os.getenv("ADE_WHEELHOUSE", ""),
        "ADE_WORKER_CPU_SECONDS": os.getenv("ADE_WORKER_CPU_SECONDS", "60"),
        "ADE_WORKER_MEM_MB": os.getenv("ADE_WORKER_MEM_MB", "512"),
        "ADE_WORKER_FSIZE_MB": os.getenv("ADE_WORKER_FSIZE_MB", "100"),
        "ADEJOB_USER": os.getenv("ADEJOB_USER", "nobody"),
    }

    proc = await asyncio.create_subprocess_exec(
        python_cmd, "-I", "-B", WORKER, str(job_id),
        cwd=str(job_dir), env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        timeout = float(os.getenv("ADE_JOB_TIMEOUT_SECONDS", "300"))
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        stdout, stderr = b"", b""

    record_event(events, event="worker.exit", job_id=job_id,
                 state=("succeeded" if proc.returncode == 0 else "failed"),
                 detail={"stderr": stderr.decode("utf-8", errors="replace")})
    return proc.returncode, stdout
```

*Why this is safe:* bugs or malicious code cannot crash your API—they only crash the **child** process.
We also limit CPU time, memory, and file sizes inside that child, and we turn **network off by default**.

---

## 7) The worker (sandboxed subprocess)

The worker sets **resource limits**, applies the resolved network policy, and then runs the ADE passes using the activation-time virtualenv, writing the artifact and the normalized workbook.

```python
# app/jobs/worker.py  (minimal but real)
import json, os, resource, socket, sys, traceback
from pathlib import Path

from backend.app.features.jobs.runtime import PipelineRunner

def apply_resource_limits():
    cpu = int(os.getenv("ADE_WORKER_CPU_SECONDS", "60"))
    mem = int(os.getenv("ADE_WORKER_MEM_MB", "512")) * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_AS, (mem, mem))

def disable_network(*, allow: bool) -> None:
    if allow:
        return

    def _blocked(*_args, **_kwargs):
        raise ConnectionError("Networking is disabled for this job")

    socket.socket = lambda *a, **k: (_blocked(*a, **k))
    socket.create_connection = lambda *a, **k: (_blocked(*a, **k))

def main() -> None:
    request = json.loads(sys.stdin.read())
    apply_resource_limits()
    allow_network = os.environ.get("ADE_RUNTIME_NETWORK_ACCESS", "0") in {"1", "true"}
    disable_network(allow=allow_network)

    manifest_path = Path(request["manifest_path"]).resolve()
    pipeline = PipelineRunner(
        config_dir=manifest_path.parent,
        manifest=json.loads(manifest_path.read_text(encoding="utf-8")),
        job_context={"job_id": request.get("job_id")},
        input_paths=[str(path) for path in request.get("input_paths", [])],
    )

    try:
        result = pipeline.execute()
        write_artifact(result)
        sys.exit(0)
    except Exception as exc:  # pragma: no cover - defensive
        traceback.print_exc()
        write_error(str(exc))
        sys.exit(1)

def write_artifact(result) -> None:
    payload = {"status": "succeeded", "tables": result.tables_summary}
    Path(os.environ["ADE_ARTIFACT_PATH"]).write_text(json.dumps(payload, indent=2), encoding="utf-8")

def write_error(message: str) -> None:
    payload = {"status": "failed", "error": message[:400]}
    Path(os.environ["ADE_ARTIFACT_PATH"]).write_text(json.dumps(payload, indent=2), encoding="utf-8")

if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
```

---

## 8) The artifact JSON (audit, not data)

The artifact is your **explainability record**.
It shows what ADE decided and why—without storing raw cell content. Think of it as “**what happened where**”.

```json
{
  "job_id": 1234,
  "summary": { "tables": 1, "rows_written": 155, "issues": 4 },
  "events": [
    { "stage": "structure", "header_row": 4, "tables": [{"range": "B4:G159"}] },
    {
      "stage": "mapping",
      "columns": [
        { "raw": {"col": "col_1", "header": "Employee ID"}, "target": "member_id", "score": 1.8,
          "contributors": [{"rule": "col.member_id.pattern", "delta": 0.9}] }
      ]
    },
    { "stage": "transform", "changed": {"member_id": 120} },
    { "stage": "validate", "errors": 3, "warnings": 1 },
    { "stage": "output", "path": "normalized.xlsx" }
  ]
}
```

> The UI can render this to explain **how** ADE turned raw rows into a normalized sheet.

---

## 9) The passes (what actually runs)

ADE runs **five ordered passes**. You don’t need to memorize them; just remember: **structure → mapping → generate**.

* **Pass 1: Structure** — find tables and headers (row detectors)
* **Pass 2: Mapping** — map raw columns to target fields (column detectors)
* **Pass 3–5: Generate** while streaming rows — transform, validate, write

Here’s a tiny bit of “mental model” pseudocode:

```python
def process_job(input_xlsx, config_pkg, artifact):
    # Find tables & header rows
    tables = detect_tables(input_xlsx, config_pkg.row_types)
    artifact.add_structure(tables)

    # Map raw columns to target fields, per table
    for t in tables:
        mapping = map_columns(input_xlsx, t, config_pkg.columns)
        artifact.add_mapping(t, mapping)

    # Stream rows: transform -> validate -> write
    with open_output_workbook("normalized.xlsx") as writer:
        for row in stream_rows(input_xlsx, tables):
            out_row = []
            for field in output_order():
                value = row[mapped_source(field)]
                value = transform(field, value, config_pkg.columns)
                issues = validate(field, value, config_pkg.columns)
                artifact.add_issues(field, row.a1, issues)
                out_row.append(value)
            writer.write_row(out_row)

    artifact.add_output("normalized.xlsx")
```

---

## 10) Back-pressure and fairness (why 429?)

We allow **N jobs** to run at once and **M jobs** to wait in line.
This prevents one user from overwhelming the server. When the queue is full, we politely ask clients to retry later.

```python
# app/routes/jobs.py (back-pressure)
try:
    app.state.job_manager.submit(job_id)
except asyncio.QueueFull:
    raise HTTPException(429, "Job queue is full. Please retry later.")
```

Set these with env vars:

* `ADE_MAX_CONCURRENCY` — workers (e.g., `2`)
* `ADE_QUEUE_SIZE` — backlog (e.g., `10`)

---

## 10) Limits and safety (why things don’t spiral)

We apply **OS rlimits** to the child process so it cannot hog CPU/RAM/disk, and we **block sockets** by default.

```python
# worker limits (already shown above)
resource.setrlimit(resource.RLIMIT_CPU,   (cpu, cpu))      # stop CPU loops
resource.setrlimit(resource.RLIMIT_AS,    (mem, mem))      # cap memory
resource.setrlimit(resource.RLIMIT_FSIZE, (fsz, fsz))      # cap file writes

# worker network toggle (off by default)
def disable_network():
    import socket
    def _blocked(*a, **k): raise ConnectionError("Networking is disabled for this job")
    socket.socket = lambda *a, **k: _blocked()
    socket.create_connection = lambda *a, **k: _blocked()
```

> If a job times out (wall clock), the parent **kills** it and marks it `ERROR: TIMEOUT`.

---

## 11) Data model (so status is reliable)

We track status and timestamps in SQLite. It’s deliberately boring—and that’s good.

```python
# app/models/job.py (sketch)
class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    workspace_id = Column(ForeignKey("workspaces.id"), nullable=False)
    document_id = Column(ForeignKey("documents.id"), nullable=False)
    config_version_id = Column(ForeignKey("configuration_script_versions.id"), nullable=False)

    status = Column(String(20), nullable=False)  # QUEUED|RUNNING|SUCCESS|ERROR
    runtime_network_access = Column(Boolean, default=False, nullable=False)
    attempts = Column(Integer, default=1, nullable=False)

    submitted_by = Column(ForeignKey("users.id"), nullable=False)
    submitted_at = Column(DateTime, default=utcnow, nullable=False)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)

    error_message = Column(Text)     # short, UI-friendly
    metrics_json = Column(JSON)      # optional
```

On startup, we reconcile:

```python
# mark in-flight as failed; requeue queued
await db.exec("UPDATE jobs SET status='ERROR', error_message='Server restarted' WHERE status='RUNNING'")
for job_id in await db.list_ids("SELECT id FROM jobs WHERE status='QUEUED'"):
    app.state.job_manager.submit(job_id)
```

---

## 12) Environment knobs (one-container friendly)

| Variable                  |   Default | What it does                                  |
| ------------------------- | --------: | --------------------------------------------- |
| `ADE_MAX_CONCURRENCY`     |       `2` | How many jobs can run at once                 |
| `ADE_QUEUE_SIZE`          |      `10` | How many jobs can wait                        |
| `ADE_JOB_TIMEOUT_SECONDS` |     `300` | Kill jobs that exceed wall time               |
| `ADE_WORKER_CPU_SECONDS`  |      `60` | CPU time cap (per job)                        |
| `ADE_WORKER_MEM_MB`       |     `512` | Memory cap (MiB)                              |
| `ADE_WORKER_FSIZE_MB`     |     `100` | Max file size a job can create (MiB)          |
| `ADE_RUNTIME_NETWORK_ACCESS` |   `false` | Default for `runtime_network_access` if omitted |
| `ADE_WHEELHOUSE`          | *(unset)* | Local wheels dir for **offline** pip installs |

---

## 13) End-to-end in 30 seconds

You submit. We queue. A worker spawns a safe subprocess. The subprocess installs only what it needs,
turns off the network, runs your passes, and drops `artifact.json` and `normalized.xlsx` in the job folder.
You poll status and download outputs. That’s it.

```bash
# Client
curl -X POST https://ade.local/jobs \
  -H "Content-Type: application/json" \
  -d '{"document_id":"doc_123","config_version_id":"cfgv_456","runtime_network_access":false}'

# Later
curl https://ade.local/jobs/1234
curl -O https://ade.local/jobs/1234/artifact
curl -O https://ade.local/jobs/1234/output
```

---

## 14) Why this works (and what we didn’t add yet)

* **Simple:** no Redis/Celery/Kubernetes—just `asyncio.Queue` + `subprocess`.
* **Safe by default:** separate interpreter, rlimits, and network off.
* **Explainable:** the artifact tells the whole story, without leaking raw data.

Future hardening (not required to ship): process groups (kill children on timeout), seccomp/bubblewrap, per-job Unix users, Prometheus metrics, cancel endpoint.

---

## 15) Copy-ready checklists

**Operator quick start**

```text
1) Set ADE_MAX_CONCURRENCY and ADE_QUEUE_SIZE for your box.
2) Keep ADE_RUNTIME_NETWORK_ACCESS=false; allow per job when truly needed.
3) Ensure /var/jobs and /var/documents are writable by the app.
4) Watch disk space; clean old /var/jobs/<id> folders periodically.
5) If queue backs up, return 429 and/or raise concurrency (carefully).
```

**Developer quick start**

```text
1) Implement the five passes behind run_passes() (or call your existing pipeline).
2) Never store raw cell values in artifact.json—only coordinates and summaries.
3) Keep transforms/validators pure and fast; the writer streams rows.
4) Surface short, user-friendly error_message from logs (tail).
```
