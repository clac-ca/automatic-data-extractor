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

Start infrastructure services:

```bash
docker compose -f docker-compose.infra.yaml up -d
```

Stop infrastructure when done:

```bash
docker compose -f docker-compose.infra.yaml down
```

## Start Services

Development mode (recommended while coding):

```bash
cd backend && uv run ade dev
```

Production-style mode (no reload behavior):

```bash
cd backend && uv run ade start
```

Stop tracked ADE service processes:

```bash
cd backend && uv run ade stop
```

Show tracked ADE service status:

```bash
cd backend && uv run ade status
```

Restart in one command (stop then start):

```bash
cd backend && uv run ade restart
```

Restart with service selection and migration control:

```bash
cd backend && uv run ade restart --services worker --no-migrate
```

`ade stop`/`ade restart` now act on tracked processes started by `ade` (state file at `.ade/state.json`).

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

All tests:

```bash
cd backend && uv run ade test
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

```bash
curl -sS http://localhost:8000/api/v1/health
curl -sS http://localhost:8001/api/v1/health
```

## If Something Fails

- Re-run `./setup.sh`.
- Check service state with `cd backend && uv run ade status`.
- If startup errors mention migrations, use [Run Migrations and Resets](run-migrations-and-resets.md).
- For runtime issues, use [Triage Playbook](../troubleshooting/triage-playbook.md).
