# ade-worker

Background worker service for ADE runs and builds.

## Overview

ade-worker is the background processor for ADE. It polls the database for queued
builds and runs, executes them, and writes NDJSON event logs and run metrics.
It is intentionally separate from the API so it can be scaled independently.

## Responsibilities

- Claim queued builds and runs from the database.
- Build isolated virtual environments per configuration build.
- Run the ADE engine CLI to validate configs or process files.
- Emit NDJSON events to per-build or per-run log files.
- Persist run metrics and extracted fields/columns back to the database.

## How it works

- **Queue source:** The worker uses the database tables as its queue.
- **Builds:** For each build, it creates a venv, installs the engine and the
  configuration package, then verifies imports.
- **Runs:** For each run, it stages the input document, invokes
  `ade_engine process file`, and streams logs/events into `events.ndjson`.
- **Backoff/leases:** Run leases are extended with a heartbeat during processing
  to avoid duplicate claims.

## Running locally (repo)

From the repo root:

```bash
# Make sure the DB schema is ready
ade migrate

# Run only the worker
ade worker
```

You can also run the module directly:

```bash
python -m ade_worker
```

## Configuration

The worker is configured by environment variables. Defaults are shown in the
settings module (`apps/ade-worker/src/ade_worker/settings.py`).

### Core ADE settings

- `ADE_DATABASE_URL` (default: `sqlite:///./data/db/ade.sqlite`)
- `ADE_DATABASE_SQLITE_JOURNAL_MODE` (default: `WAL`)
- `ADE_DATABASE_SQLITE_SYNCHRONOUS` (default: `NORMAL`)
- `ADE_DATABASE_SQLITE_BUSY_TIMEOUT_MS` (default: `30000`)
- `ADE_WORKSPACES_DIR` (default: `./data/workspaces`)
- `ADE_DOCUMENTS_DIR` (default: `ADE_WORKSPACES_DIR`)
- `ADE_CONFIGS_DIR` (default: `ADE_WORKSPACES_DIR`)
- `ADE_RUNS_DIR` (default: `ADE_WORKSPACES_DIR`)
- `ADE_VENVS_DIR` (default: `./data/venvs`)
- `ADE_PIP_CACHE_DIR` (default: `./data/cache/pip`)
- `ADE_ENGINE_SPEC` (default: `apps/ade-engine`)
- `ADE_BUILD_TIMEOUT` (default: `600`)
- `ADE_RUN_TIMEOUT_SECONDS` (default: unset)

### Worker settings

- `ADE_WORKER_CONCURRENCY` (default: `min(4, cpu_count / 2)`)
- `ADE_WORKER_POLL_INTERVAL` (default: `0.5`)
- `ADE_WORKER_POLL_INTERVAL_MAX` (default: `2.0`)
- `ADE_WORKER_CLEANUP_INTERVAL` (default: `30.0`)
- `ADE_WORKER_METRICS_INTERVAL` (default: `30.0`)
- `ADE_WORKER_ID` (default: unset; generated from host/pid/idx)
- `ADE_WORKER_JOB_LEASE_SECONDS` (default: `900`)
- `ADE_WORKER_JOB_MAX_ATTEMPTS` (default: `3`)
- `ADE_WORKER_JOB_BACKOFF_BASE_SECONDS` (default: `5`)
- `ADE_WORKER_JOB_BACKOFF_MAX_SECONDS` (default: `300`)
- `ADE_WORKER_LOG_LEVEL` (default: `INFO`)
- `ADE_LOG_LEVEL` (fallback if `ADE_WORKER_LOG_LEVEL` is unset)

## Logs and artifacts

- Build logs live under the build venv:
  `data/venvs/<workspace>/<configuration>/<build>/logs/events.ndjson`
- Run logs live under the run directory:
  `data/workspaces/<workspace>/runs/<run_id>/logs/events.ndjson`
- Run outputs are written to:
  `data/workspaces/<workspace>/runs/<run_id>/output/`

## Development

Install dev deps and run tests:

```bash
python -m pip install -e "apps/ade-worker[dev]"
pytest apps/ade-worker/tests
```
