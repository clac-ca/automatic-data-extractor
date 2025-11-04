# Job Orchestration — Queue & Workers

This page describes how ADE receives a job, schedules it, and runs it safely. A **job** is one execution of ADE
against one input file using one prepared config package. Every job writes its audit trail and outputs to a
dedicated directory under `${ADE_DATA_DIR}/jobs/<job_id>/`.

---

## Job working directory

Jobs materialize in a predictable folder layout that mirrors the broader storage tree. Because
`${ADE_DATA_DIR}` is typically mounted to durable storage in production, these folders persist across restarts,
making it easy to audit past runs.

```text
${ADE_DATA_DIR}/jobs/<job_id>/
├─ inputs/                 # Uploaded documents copied or symlinked on submit
├─ artifact.json           # Human/audit-readable record of decisions (no raw cell dumps)
├─ normalized.xlsx         # Final workbook emitted after all passes
├─ events.ndjson           # Append-only lifecycle events (enqueue, start, finish, error...)
├─ run-request.json        # Snapshot of the parameters handed to the worker subprocess
└─ .venv → ../../venvs/<config_id>/   # Symlink to the prepared environment for this config
```

The worker subprocess imports the frozen snapshot at `venvs/<config_id>/ade-build/snapshot/`. This keeps jobs
deterministic even if the author publishes a newer version later.

---

## Queue and worker

ADE keeps orchestration lightweight: a single FastAPI process owns the in-memory queue and a bounded pool of
worker subprocesses—no Redis, Celery, or external brokers to manage.

1. **Submit** — Clients call `POST /api/v1/.../jobs` with a `config_version_id`, document references, and optional
   flags such as `runtime_network_access`. If capacity is available, ADE returns `202 Accepted` and a `Location`
   header pointing at the job resource. When the queue is full, the API returns `429` with a retry hint.
2. **Reserve** — The job manager reserves a slot before committing any database rows. This prevents runaway queues
   and keeps back-pressure predictable.
3. **Enqueue** — On success, ADE persists the job record, writes an initial `run-request.json`, and places the job
   ID onto an in-memory queue.
4. **Run** — Worker processes dequeue IDs, spawn a sandboxed subprocess per job, and stream status updates into
   `events.ndjson`.

Concurrency is bounded by `ADE_MAX_CONCURRENCY`; the queue depth is capped by `ADE_QUEUE_SIZE`. Everything runs
within the main service—no external brokers or daemons.

---

## Execution pipeline

Inside the worker subprocess ADE performs the five passes defined by the config package:

1. Locate tables and header rows using `row_types/header.py` and `row_types/data.py`.
2. Map raw columns to target fields via the detectors in `columns/<field>.py`.
3. Optionally transform values.
4. Optionally validate values and emit issues.
5. Generate the normalized workbook according to the manifest.

Each stage writes structured updates into the artifact. Hooks (if present) run before the passes and after
mapping/transform/validate to annotate the audit trail.

Jobs that succeed end in status `SUCCESS`; jobs that raise or violate limits end in `ERROR` with a short,
user-facing message plus diagnostic context in `events.ndjson`.

---

## Isolation and safety

- **Sandboxed subprocess** — Each job runs in its own Python interpreter with strict resource limits set via
  `rlimit` (CPU seconds, memory, and file size).
- **Network off by default** — Socket creation is blocked unless the job explicitly requests
  `runtime_network_access`.
- **Read-only snapshot** — The worker imports from `ade-build/snapshot/`, so code cannot mutate the source
  package and past runs stay reproducible.
- **Structured logging** — Only metadata is recorded; ADE never writes raw cell values to disk outside of the
  original `inputs/` copy.
- **Graceful recovery** — On restart, queued jobs are re-submitted to the manager, and any in-flight jobs are
  marked failed with a recovery message so operators can retry.

Together these guardrails keep untrusted config code from affecting other jobs or the host.

---

## Environment controls

The job manager reads its knobs from environment variables (see [Developer Guide → Environment and
Configuration](./README.md#environment-and-configuration)). The most commonly tuned values are:

| Variable                  | Default | Purpose                                 |
| ------------------------- | ------: | ----------------------------------------|
| `ADE_MAX_CONCURRENCY`     |       2 | Number of worker subprocesses            |
| `ADE_QUEUE_SIZE`          |      10 | Maximum queued jobs before returning 429 |
| `ADE_JOB_TIMEOUT_SECONDS` |     300 | Hard wall-clock timeout per job          |
| `ADE_WORKER_CPU_SECONDS`  |      60 | CPU time cap inside the subprocess       |
| `ADE_WORKER_MEM_MB`       |     512 | Memory limit (MiB)                       |
| `ADE_WORKER_FSIZE_MB`     |     100 | Maximum file size a worker may create    |

Operators keep `runtime_network_access` disabled globally and enable it per job only when necessary.

---

## Related endpoints

- `POST /jobs` — submit
- `GET /jobs/{job_id}` — status (queued/running/success/error)
- `GET /jobs/{job_id}/artifact` — fetch the artifact
- `GET /jobs/{job_id}/output` — download `normalized.xlsx`
- `POST /jobs/{job_id}/retry` — enqueue a new attempt sharing the same document/config

These endpoints return structured JSON so the UI can poll and render progress.

---

## Next steps

- [Config Packages](./01-config-packages.md) — authoring, prepare, and hooks.
- [Artifact Reference](./14-job_artifact_json.md) — schema for the per-job audit trail.
