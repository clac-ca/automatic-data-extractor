# Run Local Dev Loop

## Goal

Set up ADE for code changes and run common developer commands.

## Before You Start

You need:

- Python 3.14+
- Node.js 22+
- `uv` (Python package manager/runner used by this repo)

## Setup

From repo root:

```bash
./setup.sh
```

This installs:

- backend dependencies in `backend/.venv`
- frontend dependencies in `frontend/ade-web/node_modules`

## Start Services

Development mode (recommended while coding):

```bash
cd backend
uv run ade dev
```

Production-style mode (no reload behavior):

```bash
cd backend
uv run ade start
```

Stop matching ADE service processes:

```bash
cd backend
uv run ade stop
```

Restart in one command (stop then start):

```bash
cd backend
uv run ade restart
```

Restart with service selection and migration control:

```bash
cd backend
uv run ade restart --services worker --no-migrate
```

`ade stop`/`ade restart` use process-signature matching and stop matching ADE API/worker/web processes, including ones started from another shell session.

## Run One Service

API only:

```bash
cd backend
uv run ade api dev
```

API multi-process dev (reload disabled):

```bash
cd backend
uv run ade api dev --processes 2
```

`ade dev` keeps API reload mode by default and ignores `ADE_API_PROCESSES`.

Worker only:

```bash
cd backend
uv run ade worker start
```

Web only:

```bash
cd backend
uv run ade web dev
```

## Tests and Lint

All tests:

```bash
cd backend
uv run ade test
```

Service-level checks:

```bash
cd backend
uv run ade api lint
uv run ade api test
uv run ade worker test
uv run ade web lint
uv run ade web test
```

## Verify

```bash
curl -sS http://localhost:8000/api/v1/health
curl -sS http://localhost:8001/api/v1/health
```

## If Something Fails

- Re-run `./setup.sh`.
- If startup errors mention migrations, use [Run Migrations and Resets](run-migrations-and-resets.md).
- For runtime issues, use [Triage Playbook](../troubleshooting/triage-playbook.md).
