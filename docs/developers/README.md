# ADE Developer Overview

This guide describes the current execution model (runs + environments) and the
core developer workflows.

---

## System model (current)

1. **Configurations** describe how ADE processes documents.
2. **Runs** are the only queued jobs created by the API.
3. **Environments** are worker-owned cached venvs keyed by configuration + dependency digest.
4. The worker provisions environments as needed and executes runs inside them.

---

## Components

* **Frontend (React Router)** — configuration editing, run initiation, workspace admin.
* **Backend (FastAPI)** — auth, metadata, document storage, run enqueueing.
* **Worker (Python)** — leases, environment provisioning, run execution, event logs.

---

## Storage layout (defaults)

Everything ADE produces is persisted under `./data/` by default.

* Workspaces: `./data/workspaces/<workspace_id>/...`
* Runs: `./data/workspaces/<workspace_id>/runs/<run_id>/...`
* Environments (venvs): `./data/venvs/<workspace_id>/<configuration_id>/<deps_digest>/<environment_id>/.venv`

Set `ADE_DATA_DIR` to relocate workspace storage and the venv root. The worker
will always nest `workspace_id` beneath the derived roots.

---

## Execution flow (happy path)

1. API inserts a `runs` row (`status=queued`).
2. Worker ensures an `environments` row exists for the run’s key fields.
3. Worker provisions the environment (if missing) and marks it `ready`.
4. Worker claims the run and executes the engine inside the environment venv.
5. Worker updates run status and writes `events.ndjson` logs.

---

## Local dev quickstart

```bash
ade dev
```

This runs the API, web app, and worker together. Use `ade dev --no-worker` when
you want to isolate the API or frontend.

---

## Notes for maintainers

* Config packages are installed **editable** in development; `.py` edits do not
  require an environment rebuild.
* Dependency manifest changes change the `deps_digest`, which triggers a new
  environment.
* GC is worker-owned; see `apps/ade-worker/README.md` for policy and settings.
