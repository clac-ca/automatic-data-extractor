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
├─ logs.txt                # stdout/stderr from the worker
└─ config/                 # the code you authored in the UI (materialized for this run)
   ├─ __init__.py
   ├─ row_types/  __init__.py  *.py
   ├─ columns/    __init__.py  *.py
   ├─ hooks/      __init__.py  *.py
   ├─ requirements.txt  (optional)
   └─ vendor/            # per-job Python deps installed here
````

---

## 2) The one-sentence model

**ADE accepts jobs via HTTP, queues them in-memory, and runs each in a separate Python subprocess with strict
resource limits and no network by default.**

```python
# high level pseudocode (not production code)
enqueue(job_id)      # POST /jobs
--N workers-->       # bounded concurrency
spawn subprocess     # one per job
  |-> set rlimits    # CPU, memory, file size, fds
  |-> install deps   # pip -t config/vendor
  |-> disable net    # unless runtime_network_access=true
  |-> run passes     # write artifact.json + normalized.xlsx
```

---

## 3) The Job API (how clients interact)

Clients create, check, and retrieve jobs over simple HTTP endpoints.

```python
# app/routes/jobs.py  (sketch)
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class SubmitJob(BaseModel):
    config_version_id: str
    document_ids: list[str] = []
    runtime_network_access: bool = False

@router.post("/jobs", status_code=202)
async def submit_job(payload: SubmitJob):
    # 1) refuse when queue/backlog is full
    if app.state.job_manager.queue_full():
        raise HTTPException(429, "Job queue is full. Please retry later.")
    # 2) create job row + materialize /var/jobs/<id>/ (inputs/*, config/*)
    job_id = await create_job_and_files(payload)
    # 3) enqueue
    app.state.job_manager.submit(job_id)
    return {"job_id": job_id, "status": "QUEUED"}

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
async def retry_job(job_id: int):
    await reset_job_outputs(job_id)     # wipe artifact/output/logs
    await set_status(job_id, "QUEUED")
    app.state.job_manager.submit(job_id)
    return {"job_id": job_id, "status": "QUEUED"}
```

---

## 4) The queue (bounded work-in-progress)

We use an **in-process** queue with a fixed number of **workers**. This keeps the API responsive and
prevents overload: if the queue is full, requests get **HTTP 429**.

```python
# app/jobs/manager.py  (sketch)
import os, asyncio, sys, datetime as dt

class JobManager:
    def __init__(self, max_workers: int, max_queue: int):
        self.queue = asyncio.Queue(maxsize=max_queue)
        self.max_workers = max_workers
        self._workers = []

    async def start(self):
        for i in range(self.max_workers):
            self._workers.append(asyncio.create_task(self._loop(i)))

    def queue_full(self) -> bool:
        return self.queue.full()

    def submit(self, job_id: int):
        self.queue.put_nowait(job_id)

    async def _loop(self, worker_id: int):
        while True:
            job_id = await self.queue.get()
            try:
                await self._process(job_id)
            finally:
                self.queue.task_done()

    async def _process(self, job_id: int):
        await db.update(job_id, status="RUNNING", started_at=dt.datetime.utcnow())
        rc, error = await self._spawn(job_id)       # see next section
        await db.update(job_id,
                        status=("SUCCESS" if rc == 0 else "ERROR"),
                        finished_at=dt.datetime.utcnow(),
                        error_message=error)

# Startup hook (e.g., app lifespan)
job_manager = JobManager(
    max_workers=int(os.getenv("ADE_MAX_CONCURRENCY", "2")),
    max_queue=int(os.getenv("ADE_QUEUE_SIZE", "10")),
)
await job_manager.start()
app.state.job_manager = job_manager
```

---

## 5) Spawning the worker (the safety boundary)

Each job runs in **its own Python process**. That process sees only the standard library plus the job’s
`config/` and `config/vendor/` folders on `PYTHONPATH`. We skip global site‑packages and capture all output to `logs.txt`.

```python
# app/jobs/manager.py  (spawn sketch)
import asyncio, os, sys, pathlib

WORKER = "/app/app/jobs/worker.py"        # absolute path to our worker script

async def _spawn(self, job_id: int):
    job_dir = pathlib.Path(f"/var/jobs/{job_id}")
    log = open(job_dir / "logs.txt", "a", buffering=1)  # line-buffered

    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        # Only the job’s code & deps are importable:
        "PYTHONPATH": f"{job_dir}/config/vendor:{job_dir}/config",
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
        sys.executable, "-S", "-B", WORKER, str(job_id),
        cwd=str(job_dir), env=env, stdout=log, stderr=log
    )

    try:
        timeout = float(os.getenv("ADE_JOB_TIMEOUT_SECONDS", "300"))
        await asyncio.wait_for(proc.wait(), timeout=timeout)
        return proc.returncode, (None if proc.returncode == 0 else _tail_error(job_dir))
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 1, f"TIMEOUT (>{int(timeout)}s)"

def _tail_error(job_dir: pathlib.Path) -> str:
    try:
        with open(job_dir / "logs.txt", "r") as fh:
            lines = [ln.strip() for ln in fh.readlines() if ln.strip()]
        return lines[-1][:240] if lines else "Job failed"
    except Exception:
        return "Job failed"
```

*Why this is safe:* bugs or malicious code cannot crash your API—they only crash the **child** process.
We also limit CPU time, memory, and file sizes inside that child, and we turn **network off by default**.

---

## 6) The worker (sandboxed subprocess)

The worker sets **resource limits**, optionally **installs dependencies** into `config/vendor/`, **disables sockets**, and then runs the ADE passes, writing the artifact and the normalized workbook.

```python
# app/jobs/worker.py  (minimal but real)
import os, sys, json, subprocess, traceback, resource

def set_limits():
    cpu = int(os.getenv("ADE_WORKER_CPU_SECONDS", "60"))
    mem = int(os.getenv("ADE_WORKER_MEM_MB", "512")) * 1024 * 1024
    fsz = int(os.getenv("ADE_WORKER_FSIZE_MB", "100")) * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_CPU,   (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_AS,    (mem, mem))
    resource.setrlimit(resource.RLIMIT_FSIZE, (fsz, fsz))

def drop_privileges():
    try:
        import pwd
        user = os.getenv("ADEJOB_USER", "nobody")
        pw = pwd.getpwnam(user)
        os.setgid(pw.pw_gid); os.setuid(pw.pw_uid)
    except Exception as e:
        print(f"[worker] privilege drop skipped: {e}", file=sys.stderr)

def disable_network():
    import socket
    def _blocked(*a, **k): raise ConnectionError("Networking is disabled for this job")
    socket.socket = lambda *a, **k: _blocked()
    socket.create_connection = lambda *a, **k: _blocked()

def install_deps_if_any():
    req = os.path.join("config", "requirements.txt")
    if not os.path.exists(req): return
    cmd = [sys.executable, "-m", "pip", "install", "-t", "config/vendor", "-r", req, "--no-cache-dir"]
    if os.getenv("ADE_RUNTIME_NETWORK_ACCESS_JOB", "false") != "true":
        cmd += ["--no-index"]
        wh = os.getenv("ADE_WHEELHOUSE")
        if wh: cmd += [f"--find-links={wh}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout, end=""); print(res.stderr, end="", file=sys.stderr)
    if res.returncode != 0: raise RuntimeError("Dependency installation failed")

def run_passes():
    # This is where your existing pass implementations are invoked.
    # Pseudocode: structure → mapping → transform → validate → write
    artifact = {"events": []}
    # structure():
    artifact["events"].append({"stage": "structure", "status": "ok"})
    # mapping():
    artifact["events"].append({"stage": "mapping", "status": "ok"})
    # transform():
    artifact["events"].append({"stage": "transform", "status": "ok"})
    # validate():
    artifact["events"].append({"stage": "validate", "status": "ok"})
    # write normalized.xlsx:
    artifact["events"].append({"stage": "output", "status": "ok"})
    return artifact

def main():
    _job_id = int(sys.argv[1])
    set_limits()
    drop_privileges()
    install_deps_if_any()
    if os.getenv("ADE_RUNTIME_NETWORK_ACCESS_JOB", "false") != "true":
        disable_network()

    try:
        artifact = run_passes()
        with open("artifact.json", "w") as f: json.dump(artifact, f, indent=2)
        sys.exit(0)
    except Exception as e:
        traceback.print_exc()
        with open("artifact.json", "w") as f:
            json.dump({"error": str(e)[:400], "events": []}, f, indent=2)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## 7) The artifact JSON (audit, not data)

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

## 8) The passes (what actually runs)

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

## 9) Back-pressure and fairness (why 429?)

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
