# 02 — Job Orchestration (Deep Dive)

ADE runs every job inside the storage tree rooted at `${ADE_DATA_DIR}`. During development that path defaults to
`./data`; in production it is typically mounted to durable storage so jobs, artifacts, and logs persist across
deploys and restarts.

The rest of this page is a deep dive into how those jobs move from HTTP submission to a finished workbook and
artifact. The emphasis is on *explainability* (the artifact JSON), *safety* (sandboxed subprocesses), and
*determinism* (prepare once, run many).

---

## 0) Start with the Artifact JSON (the backbone)

**Artifact JSON** is both:

1. **Audit record** — a full narrative of the run (what ADE saw, decided, and wrote).
2. **Shared state** — the *only* object passed between passes (append-only during the run).

**Design guarantees**

* **Append-only during execution:** passes add facts; they don’t rewrite history.
* **No raw cell values:** the artifact records *locations* (A1), *decisions*, *contributors*, and *summaries*—never the underlying data.
* **Reproducibility:** a **rule registry** logs the exact code identifiers + content hashes for all callables.

### Initial artifact shape (created before Pass 1)

```json
{
  "version": "artifact.v1.1",
  "job":     { "id": "<job_id>", "source_file": "input.xlsx", "started_at": "2025-10-30T12:34:56Z" },
  "config":  { "workspace_id": "<ws>", "config_id": "<active-config-id>", "title": "Membership Rules", "version": "1.2.0" },
  "rules":   {},          // rule registry (filled immediately after init)
  "sheets":  [],          // filled by Pass 1 (structure)
  "output":  {},          // filled by Pass 3–5 (generate)
  "summary": {},          // filled at end
  "pass_history": []      // appended after each pass completes
}
```

### Building the rule registry (what code ran?)

```python
def build_rule_registry(config_pkg) -> dict:
    registry = {}
    for rule in discover_rules(config_pkg):  # row detectors, column detectors, transforms, validators, hooks
        impl = f"{rule.module}:{rule.func}"  # e.g., "columns/member_id.py:detect_synonyms"
        src  = read_source(rule.module, rule.func)
        ver  = sha1(src)[:6]                 # short content hash
        registry[rule.rule_id] = {"impl": impl, "version": ver}
    return registry
```

> See **Artifact Reference** (`./14-job_artifact_json.md`) for the full schema.

---

## 1) Job storage layout

Every job writes to `${ADE_DATA_DIR}/jobs/<job_id>/`. Because `${ADE_DATA_DIR}` is usually a shared,
durable mount in production, job folders persist across restarts, making later audits easy.

```text
${ADE_DATA_DIR}/jobs/<job_id>/
├─ inputs/                 # Uploaded documents copied or symlinked on submit
├─ artifact.json           # Human/audit-readable record of decisions (no raw cell dumps)
├─ normalized.xlsx         # Final workbook emitted after all passes
├─ events.ndjson           # Append-only lifecycle events (enqueue, start, finish, error…)
├─ run-request.json        # Snapshot of parameters handed to the worker subprocess
└─ .venv → ../../venvs/<config_id>/   # Symlink to the prepared environment for this config
```

The worker subprocess imports the frozen snapshot at `venvs/<config_id>/ade-build/snapshot/`. This keeps jobs
deterministic even when the author publishes a newer version later.

---

## 2) Orchestration at a glance

```
Start
  │
  ├─ Build initial artifact
  │   └─ attach rule registry (impl + hash)
  │
  ├─ Pass 1: Structure
  │   └─ stream rows → label (header/data/separator) → infer tables + A1 ranges
  │
  ├─ Pass 2: Mapping
  │   └─ sample raw columns → score per target field → pick / leave unmapped
  │
  ├─ (Pass 2.5: Analyze)  ← optional tiny stats for sanity checks
  │
  ├─ Pass 3–5: Generate
  │   └─ for each row: Transform → Validate → Write → record summaries/issues
  │
  └─ Finish
      ├─ normalized.xlsx
      └─ artifact.json (full narrative)
```

**Streaming I/O:** ADE never requires full-sheet loads. Row scanning and writing are streaming; column work can use samples or chunked scans.

---

## 3) Contracts your code must follow (tiny shapes)

* **Row/column detectors:** return **score deltas** (additive hints).  
  `{"scores": {"header": +0.6}}` or `{"scores": {field_name: +0.4}}`
* **Transforms:** return new values for the column + optional warnings.  
  `{"values": [...], "warnings": [...]}`
* **Validators:** return issues (no data changes).  
  `{"issues": [{"row_index": 12, "code": "required_missing", ...}]}`
* **Hooks:** may return `{"notes": "..."}` to annotate history.

All public functions are **keyword-only** and must tolerate extra kwargs via `**_`.

---

## 4) Pseudocode — the orchestrator

> The following pseudocode is faithful to ADE’s control flow but simplified for clarity.

```python
def run_job(source_file, active_config):
    artifact = make_initial_artifact(source_file, active_config)
    artifact["rules"] = build_rule_registry(active_config)
    save_artifact_atomic(artifact)

    # Pass 1: Structure (find tables & headers)
    pass1_structure(source_file, active_config, artifact)
    save_artifact_atomic(artifact)

    # Pass 2: Mapping (raw columns → target fields)
    pass2_mapping(source_file, active_config, artifact)
    save_artifact_atomic(artifact)

    # Optional tiny stats
    if analyze_enabled(active_config):
        pass2_5_analyze(source_file, active_config, artifact)
        save_artifact_atomic(artifact)

    # Pass 3–5: Generate (transform → validate → write)
    pass3_to_5_generate(source_file, active_config, artifact)
    save_artifact_atomic(artifact, finalize=True)

    return artifact
```

`save_artifact_atomic` writes to a temp file and renames, so crashes don’t corrupt the narrative.

---

## 5) Pass 1 — Structure (find tables & headers)

**Goal:** Identify table regions and header rows by *streaming* each sheet and labeling each row.

**Reads:** initial artifact, row detector functions, manifest ordering for ties  
**Writes:** `artifact["sheets"]` → sheet summaries with table ranges and header decisions

```python
def pass1_structure(source_file, config, artifact):
    for sheet in stream_sheets(source_file):
        tables = []
        for row in sheet.rows():
            scores = aggregate(detector(row) for detector in config.row_detectors)
            label = choose_best_label(scores, config.manifest["engine"]["row_types"]["order"])
            update_state(tables, row.index, label)
        finalize_tables(tables)
        artifact["sheets"].append({"name": sheet.name, "tables": tables})
    mark_pass_done(artifact, 1, "structure")
```

**Detector return shape**  
`{"scores": {"header": +0.6, "data": -0.1}}`

**Table inference rules**

* Adjacent `data` blocks with the same header merge.
* Separator rows reset the table accumulator.
* If no header is found before data, ADE synthesizes `["Column 1", ...]`.

---

## 6) Pass 2 — Mapping (raw columns → target fields)

**Goal:** For each table, map raw columns to manifest-defined target fields—or leave them unmapped.

**Reads:** `artifact["sheets"][*]["tables"]`, column detectors, manifest metadata (synonyms, patterns)  
**Writes:** `artifact["sheets"][*]["tables"][*]["mapping"]` + contributor breakdown

```python
def pass2_mapping(source_file, config, artifact):
    for sheet in artifact["sheets"]:
        for table in sheet["tables"]:
            sample = sample_columns(source_file, sheet["name"], table["a1_range"])
            mapping = []
            for raw in sample.columns:
                totals, contributors = score_column(raw, config, table)
                best_field = choose_best_field(totals, config.manifest["columns"]["order"])
                if exceeds_threshold(best_field, totals, config):
                    mapping.append({"raw": raw.meta, "target_field": best_field, "score": totals[best_field], "contributors": contributors[best_field]})
                else:
                    mapping.append({"raw": raw.meta, "target_field": None, "score": 0.0, "contributors": []})
            table["mapping"] = mapping
    mark_pass_done(artifact, 2, "mapping")
```

**Detector return shape**  
`{"scores": {field_name: +0.4}}`

**Tie-breaking & thresholds**

* Highest score wins; ties fall back to manifest order.
* `engine.defaults.mapping_score_threshold` guards against low-confidence guesses. If max score `< threshold`, ADE leaves the column unmapped (`target_field: null`).

---

## 7) Passes 3–5 — Generate (transform → validate → write)

ADE streams each table row by row. For every mapped target field it:

1. Reads the raw value from the column mapping.
2. Runs `transform` (optional).
3. Runs `validate` (optional).
4. Appends issues (if any) to `artifact["sheets"][...]["tables"][...]["validation"]["issues"]`.
5. Writes the transformed value to the normalized workbook (streaming writer).

```python
def pass3_to_5_generate(source_file, config, artifact):
    writer = open_normalized_workbook()
    for sheet in artifact["sheets"]:
        for table in sheet["tables"]:
            for row in stream_table_rows(source_file, sheet["name"], table):
                output_row = []
                for field in config.manifest["columns"]["order"]:
                    ctx = make_context(field, row, table, config, artifact)
                    value = row.get_value(field, table["mapping"])
                    value = run_transform(field, value, ctx, artifact)
                    issues = run_validate(field, value, ctx, artifact)
                    append_issues(table, issues, row)
                    output_row.append(value)
                writer.write_row(sheet["name"], table["id"], output_row)
    writer.save("normalized.xlsx")
    artifact.setdefault("output", {})["normalized_workbook"] = "normalized.xlsx"
    mark_pass_done(artifact, 3, "transform")
    mark_pass_done(artifact, 4, "validate")
    mark_pass_done(artifact, 5, "write")
    finalize_summary(artifact)
```

Transforms return `{"values": [...], "warnings": [...]}`; validators return `{"issues": [...]}`.

---

## 8) Hooks (before/after passes)

Hook files live under `hooks/` inside the config package and run inside the same sandboxed context.

| Hook file            | When it runs                    | Good for…                        |
| -------------------- | ------------------------------- | -------------------------------- |
| `on_job_start.py`    | Before ADE begins processing    | Warming caches, logging metadata |
| `after_mapping.py`   | After Pass 2 (Map Columns)      | Inspecting or adjusting mapping  |
| `after_transform.py` | After Pass 3 (Transform Values) | Summaries, downstream triggers   |
| `after_validate.py`  | After Pass 4 (Validate Values)  | Aggregating issues, dashboards   |

Hook signature:

```python
def run(
    *,
    artifact: dict,                   # read-only artifact (empty or near-empty at this point)
    manifest: dict,                   # parsed manifest.json
    env: dict | None = None,          # environment values from manifest
    job_id: str,                      # job identifier
    source_file: str,                 # original file path/name
    **_
) -> dict | None:
    """
    Optional return:
      {"notes": "short message for audit trail"}
    """
```

---

## 9) Queue, workers, and back-pressure

ADE keeps orchestration lightweight: a single FastAPI process owns an in-memory queue and a bounded pool of
worker subprocesses—no Redis, Celery, or external brokers to manage.

1. **Submit** — Clients call `POST /api/v1/.../jobs` with a `config_version_id`, document references, and optional
   flags such as `runtime_network_access`. If capacity is available, ADE returns `202 Accepted` and a `Location`
   header pointing at the job resource. When the queue is full, the API returns `429` with a retry hint.
2. **Reserve** — The job manager reserves a slot before committing any database rows. This prevents runaway queues
   and keeps back-pressure predictable.
3. **Enqueue** — On success, ADE persists the job record, writes an initial `run-request.json`, and places the job
   ID onto the in-memory queue.
4. **Run** — Worker processes dequeue IDs, spawn a sandboxed subprocess per job, and stream status updates into
   `events.ndjson`.

Concurrency is bounded by `ADE_MAX_CONCURRENCY`; the queue depth is capped by `ADE_QUEUE_SIZE`.

```python
# app/jobs/manager.py  (sketch)
class JobManager:
    def __init__(self, max_workers: int, max_queue: int):
        self.queue = asyncio.Queue(maxsize=max_queue)
        self.max_workers = max_workers
        self._workers: list[asyncio.Task[None]] = []

    async def start(self):
        for i in range(self.max_workers):
            self._workers.append(asyncio.create_task(self._loop(i)))

    def try_reserve(self) -> bool:
        if self.queue.full():
            return False
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
```

---

## 10) Prepared environment (per config virtualenv)

Every config version owns a **dedicated virtual environment** built during prepare, not at job time.

1. Detect `requirements.txt` inside the package.
2. Create `${ADE_DATA_DIR}/venvs/<config_id>/`.
3. Run `pip install -r requirements.txt` and capture `pip freeze` into `ade-build/packages.txt`.
4. Snapshot scripts into `ade-build/snapshot/` and record metadata (including the interpreter path) in `ade-build/build.json`.

Jobs then mount `.venv → ../../venvs/<config_id>/` and import exclusively from that frozen snapshot.

---

## 11) Spawning the worker (the safety boundary)

Each job runs in **its own Python process**. That process sees only the standard library plus the job’s
config snapshot on `PYTHONPATH`. Global site-packages are skipped and all output is captured.

```python
import os
from pathlib import Path

async def _spawn(self, job_id: int):
    data_dir = Path(os.environ.get("ADE_DATA_DIR", "./data")).resolve()
    job_dir = data_dir / "jobs" / str(job_id)
    python_cmd = job_dir / ".venv" / "bin" / "python"
    snapshot = job_dir / ".venv" / "ade-build" / "snapshot"
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": str(snapshot),
        "ADE_RUNTIME_NETWORK_ACCESS": str(await db.get_runtime_network_access(job_id)).lower(),
        "ADE_WORKER_CPU_SECONDS": os.getenv("ADE_WORKER_CPU_SECONDS", "60"),
        "ADE_WORKER_MEM_MB": os.getenv("ADE_WORKER_MEM_MB", "512"),
        "ADE_WORKER_FSIZE_MB": os.getenv("ADE_WORKER_FSIZE_MB", "100"),
    }
    proc = await asyncio.create_subprocess_exec(
        str(python_cmd), "-I", "-B", WORKER, str(job_id),
        cwd=str(job_dir), env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    return await proc.communicate()
```

*Why this is safe:* bugs or malicious code crash only the child process. CPU, memory, and file size are limited via `rlimit`, and network sockets are blocked unless explicitly allowed.

---

## 12) Safe mode (`ADE_SAFE_MODE`)

When `ADE_SAFE_MODE=true`, ADE refuses to execute config code while keeping the API/UI available.

- Job submissions are rejected with HTTP 400 (`JobSubmissionError`) and a diagnostic message.
- Worker subprocesses are never spawned.
- `/api/v1/health` reports a `degraded` safe-mode component.
- The frontend surfaces a banner, disables “Run extraction,” and points operators back to the toggle.
- Existing artifacts remain downloadable; flip the flag off and restart once the config is fixed.

Use safe mode as an escape hatch after deploying a bad config—pause execution, roll back, then resume.

---

## 13) The worker subprocess (sandboxed runtime)

```python
# app/jobs/worker.py  (minimal but real)
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
    socket.socket = lambda *a, **k: _blocked(*a, **k)
    socket.create_connection = lambda *a, **k: _blocked(*a, **k)

def main() -> None:
    request = json.loads(sys.stdin.read())
    apply_resource_limits()
    allow_network = os.environ.get("ADE_RUNTIME_NETWORK_ACCESS", "false") in {"1", "true"}
    disable_network(allow=allow_network)
    pipeline = PipelineRunner(... request ...)
    try:
        result = pipeline.execute()
        write_artifact(result)
        sys.exit(0)
    except Exception as exc:
        write_error(str(exc))
        sys.exit(1)
```

---

## 14) Error handling & determinism

**Rule failures are contained:** if a detector/transform/validator raises, ADE records a neutral result and
appends a rule-error entry to the artifact, then continues.

```python
def safe_call(rule_id, fn, **kwargs):
    try:
        return fn(**kwargs) or {}
    except Exception as e:
        artifact = kwargs.get("artifact")
        if artifact is not None:
            artifact.setdefault("rule_errors", []).append({"rule": rule_id, "message": str(e), "at": now_iso()})
        return {}
```

**Determinism:** Keep rules pure (no global state, no unseeded randomness).  
**Security:** Runtime is sandboxed with time/memory limits; network is off by default.

---

## 15) Resumability & atomic writes

Because the artifact is saved atomically after each pass, jobs can resume safely:

```python
def resume_if_needed(artifact):
    done = {p["pass"] for p in artifact.get("pass_history", [])}
    if 1 not in done: pass1_structure(...)
    if 2 not in done: pass2_mapping(...)
    if not {3, 4, 5}.issubset(done):
        pass3_to_5_generate(...)
```

---

## 16) Practical debugging (reading the artifact)

**Explain a mapping decision**

```python
def explain_mapping(artifact, table_id, raw_column_id):
    for s in artifact["sheets"]:
        for t in s["tables"]:
            if t["id"] == table_id:
                for m in t.get("mapping", []):
                    if m["raw"]["column"] == raw_column_id:
                        return {"target_field": m["target_field"], "score": m["score"], "contributors": m.get("contributors", [])}
```

**List validation errors with coordinates**

```python
def list_errors(artifact):
    items = []
    for s in artifact["sheets"]:
        for t in s["tables"]:
            for issue in t.get("validation", {}).get("issues", []):
                items.append((s.get("name"), t["id"], issue["a1"], issue["message"]))
    return items
```

---

## 17) Environment controls (one-container friendly)

| Variable                  | Default | Purpose                                   |
| ------------------------- | ------: | ------------------------------------------|
| `ADE_MAX_CONCURRENCY`     |       2 | Worker subprocess count                    |
| `ADE_QUEUE_SIZE`          |      10 | Queue backlog before returning 429         |
| `ADE_JOB_TIMEOUT_SECONDS` |     300 | Hard wall-clock timeout per job            |
| `ADE_WORKER_CPU_SECONDS`  |      60 | CPU time cap inside the subprocess         |
| `ADE_WORKER_MEM_MB`       |     512 | Memory limit (MiB)                         |
| `ADE_WORKER_FSIZE_MB`     |     100 | Maximum file size a worker may create (MiB)|
| `ADE_RUNTIME_NETWORK_ACCESS` | false | Default network policy for jobs             |

Operators keep `runtime_network_access` disabled globally and enable it per job only when necessary.

---

## 18) End-to-end in 30 seconds

You submit. ADE queues. A worker spawns a safe subprocess. The subprocess runs the passes, writes
`artifact.json` and `normalized.xlsx`, and exits. You poll for status and download outputs.

```bash
curl -X POST https://ade.local/jobs \
  -H "Content-Type: application/json" \
  -d '{"document_id":"doc_123","config_version_id":"cfgv_456","runtime_network_access":false}'

curl https://ade.local/jobs/1234
curl -O https://ade.local/jobs/1234/artifact
curl -O https://ade.local/jobs/1234/output
```

---

## 19) Related endpoints

- `POST /jobs` — submit
- `GET /jobs/{job_id}` — status (queued/running/success/error)
- `GET /jobs/{job_id}/artifact` — download the artifact
- `GET /jobs/{job_id}/output` — download `normalized.xlsx`
- `POST /jobs/{job_id}/retry` — enqueue a new attempt sharing the same document/config

These return structured JSON so the UI can poll and render progress.

---

## 20) What to read next

* **Config Packages** → `./01-config-packages.md`
* **Artifact Reference** → `./14-job_artifact_json.md`
* **Pass guides** → `./03-pass-find-tables-and-headers.md` through `./07-pass-generate-normalized-workbook.md`

Together they explain how ADE keeps jobs isolated, reproducible, and fully auditable.
