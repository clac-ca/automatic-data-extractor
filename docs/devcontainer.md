# Devcontainer (Clone-and-Go)

This repo is set up to run **fully locally** in a VS Code Dev Container:

- Workspace container: Python 3.12
- Local dependencies (Docker Compose):
  - Postgres 18 (Linux container)
  - Azurite (Azure Storage emulator, blob-only)

## Prerequisites

- Docker Desktop (or Docker Engine)
- VS Code + "Dev Containers" extension

## Quickstart

1) Clone the repo

2) Create your env file:

```bash
cp .env.example .env
```

3) Open the repo in VS Code and choose:

**"Dev Containers: Reopen in Container"**

4) The devcontainer will automatically run:

```bash
./setup.sh
```

## Run the stack (dev)

Start everything (API + worker + web dev server):

```bash
ade dev
```

Or run components separately:

```bash
ade dev --api
ade dev --worker
ade dev --web
```

## Ports

- API: 8000
- Web dev server: 5173
- Postgres: 5432
- Azurite blob: 10000

## What starts by default?

The devcontainer uses the root `docker-compose.yml` plus the
`.devcontainer/docker-compose.devcontainer.override.yml` override and starts:

- `postgres` on port 5432
- `azurite` on port 10000 (blob-only)

The app container is named `ade`.
The devcontainer override swaps the `ade` service to a local dev image target
and bind-mounts the repo for editable installs.

## Connection details

### Postgres (local container)

Inside the devcontainer network:

- Host: `postgres`
- Port: `5432`
- User: `ade`
- Password: from `.env` inside `ADE_DATABASE_URL`
- App setting: `ADE_DATABASE_URL` (canonical SQLAlchemy URL)

From your host machine (because the compose file publishes ports):

- Host: `localhost`
- Port: `5432`

#### TLS settings

Local dev defaults (from `.env.example`):

- `ADE_DATABASE_URL=postgresql+psycopg://ade:ade@postgres:5432/ade?sslmode=disable`

For production, prefer `verify-full` plus `ADE_DATABASE_SSLROOTCERT`.

### Azurite (local storage emulator)

Inside the devcontainer network:

- Blob:  `http://azurite:10000/devstoreaccount1`

From your host machine:

- Blob:  `http://127.0.0.1:10000/devstoreaccount1`

**Note:** Azurite does not support Azure AD credentials. To use Azurite with ADE,
provide `ADE_BLOB_CONNECTION_STRING` plus `ADE_BLOB_CONTAINER`, and disable
versioning (`ADE_BLOB_REQUIRE_VERSIONING=false`).
For AAD/Managed Identity auth, use a real Azure Storage account with
`ADE_BLOB_ACCOUNT_URL`.

## Switching to Azure (env-only)

You do not need to change code or rebuild images.

- To use Azure Database for PostgreSQL: set `ADE_DATABASE_URL` to your Azure DSN and
  `ADE_DATABASE_AUTH_MODE=managed_identity` for Entra auth (or keep `password`). Use
  `sslmode=verify-full` in the URL and set `ADE_DATABASE_SSLROOTCERT` when required.
- To use Azure Storage: set `ADE_BLOB_CONTAINER`, plus one of:
  `ADE_BLOB_ACCOUNT_URL` (managed identity) or
  `ADE_BLOB_CONNECTION_STRING` (connection string/Azurite).

Local containers may still be running, but the app will connect to Azure based on env values.

## Cleaning

Safe cleanup (no data deletion):

```bash
bash scripts/ops/clean-artifacts.sh
```

Full cleanup (removes node_modules):

```bash
bash scripts/ops/clean-artifacts.sh --all
```

Destructive reset (drops DB tables + removes ADE storage under `data/`):

```bash
bash scripts/ops/reset-storage.sh --yes
```

Reset Postgres + Azurite Docker volumes (devcontainer services only):
Use `docker volume ls` and remove the devcontainer volumes manually, or remove the
containers and volumes with `docker compose -f docker-compose.yml -f .devcontainer/docker-compose.devcontainer.override.yml down -v`.
