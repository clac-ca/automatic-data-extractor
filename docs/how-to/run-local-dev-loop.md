# Run Local Dev Loop

## Goal

Set up ADE for code changes with native local processes and containerized infrastructure.

## Before You Start

You need:

- Python `>=3.13,<3.15`
- Node.js `>=20,<23`
- `uv` (used for backend environment and runtime worker venv builds)
- Docker (for Postgres + Azurite infra)

## Setup

From repo root:

```bash
./setup.sh
```

This installs:

- backend dependencies in `backend/.venv`
- frontend dependencies in `frontend/node_modules`
- local infra profile keys in `.env`

To start local infrastructure during setup:

```bash
./setup.sh --with-infra
```

To start ADE immediately after setup and open a browser when the web service is reachable:

```bash
./setup.sh --open
```

If you already ran setup and only want to manage infrastructure:

```bash
cd backend && uv run ade infra up -d --wait
```

`ade infra up` accepts the same runtime flags as `docker compose up`, including `-d` and `--wait`.

Stop infrastructure when done:

```bash
cd backend && uv run ade infra down
```

Force-regenerate deterministic local defaults:

```bash
./setup.sh --with-infra --force
# or
cd backend && uv run ade infra up --force
```

## Start Services

Development mode (recommended while coding):

```bash
cd backend && uv run ade dev
```

Open browser automatically while starting services:

```bash
cd backend && uv run ade dev --open
```

Production-style mode (no reload behavior):

```bash
cd backend && uv run ade start
```

## Run One Service

API only:

```bash
cd backend && uv run ade api dev
```

API multi-process dev (reload disabled):

```bash
cd backend && uv run ade api dev --processes 2
```

`ade dev` keeps API reload mode by default and ignores `ADE_API_PROCESSES`.

Worker only:

```bash
cd backend && uv run ade worker start
```

Web only:

```bash
cd backend && uv run ade web dev
```

## Tests and Lint

Default test pass (API unit + worker unit + web tests):

```bash
cd backend && uv run ade test
```

Integration suites (requires explicit `ADE_TEST_*` settings):

```bash
cd backend && \
ADE_TEST_DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ade_test?sslmode=disable' \
ADE_TEST_BLOB_CONNECTION_STRING='UseDevelopmentStorage=true' \
uv run ade api test integration

cd backend && \
ADE_TEST_DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ade_test?sslmode=disable' \
uv run ade worker test integration
```

Service-level checks:

```bash
cd backend && uv run ade api lint
cd backend && uv run ade api test
cd backend && uv run ade worker test
cd backend && uv run ade web lint
cd backend && uv run ade web test
```

## Verify

Show resolved local URLs first:

```bash
cd backend && uv run ade infra info
```

Then call health endpoints using the reported web/API ports, for example:

```bash
curl -sS http://localhost:8000/api/v1/health
curl -sS http://localhost:8001/api/v1/health
```

## If Something Fails

- Re-run `./setup.sh`.
- If `ade dev` reports missing local runtime settings or unreachable local infra, run `cd backend && uv run ade infra up`.
- In devcontainers, ADE now uses `/app/.venv` for Python tooling and
  `/app/data` for runtime state. Rebuild/reopen the container after path-related
  config changes.
- If startup errors mention migrations, use [Run Migrations and Resets](run-migrations-and-resets.md).
- For runtime issues, use [Triage Playbook](../troubleshooting/triage-playbook.md).
