# Devcontainer (Clone-and-Go)

This repo is set up to run **fully locally** in a VS Code Dev Container:

- Workspace container: Python 3.12 + Microsoft ODBC Driver 18
- Local dependencies (Docker Compose):
  - SQL Server (Linux container)
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
bash scripts/dev/bootstrap.sh
```

> If you do not work on the web UI (apps/ade-web), you can skip web setup:
>
> ```bash
> bash scripts/dev/bootstrap.sh --no-web
> ```

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
- SQL Server: 1433
- Azurite blob: 10000

## What starts by default?

The devcontainer uses `.devcontainer/docker-compose.yml` and starts:

- `sql` on port 1433
- `azurite` on port 10000 (blob-only)

The app container is named `ade`.

## Connection details

### SQL Server (local container)

Inside the devcontainer network:

- Host: `sql`
- Port: `1433`
- User: `sa`
- Password: from `.env` (`ADE_SQL_PASSWORD`)
- App setting: `ADE_SQL_*` values are used to build the SQL Server DSN

From your host machine (because the compose file publishes ports):

- Host: `localhost`
- Port: `1433`

#### ODBC Driver 18 encryption gotcha (important)

ODBC Driver 18 enables encryption by default. Local SQL containers typically use self-signed certs,
so you will usually want **optional encryption** for local dev.

Default local dev values (from `.env.example`):

- `ADE_SQL_ENCRYPT=yes`
- `ADE_SQL_TRUST_SERVER_CERTIFICATE=yes`
These settings are used when ADE builds the SQL Server DSN from `ADE_SQL_*`.

If you're using `sqlcmd`, the equivalent is:

```bash
bash scripts/db/wait-for-sql.sh
```

(It uses `sqlcmd -No` for optional encryption.)

### Azurite (local storage emulator)

Inside the devcontainer network:

- Blob:  `http://azurite:10000/devstoreaccount1`

From your host machine:

- Blob:  `http://127.0.0.1:10000/devstoreaccount1`

**Note:** Azurite uses an *IP-style URL* where the account name is in the URL path.

## Switching to Azure (env-only)

You do not need to change code or rebuild images.

- To use Azure SQL: set `ADE_SQL_HOST`, `ADE_SQL_DATABASE`, `ADE_SQL_USER`,
  and `ADE_SQL_PASSWORD` (or set `ADE_DATABASE_AUTH_MODE=managed_identity` for Entra auth).
- To use Azure Storage: set `ADE_STORAGE_CONNECTION_STRING` to your real Azure connection string.

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

Destructive reset (drops DB tables + removes persisted SQL/Azurite data):

```bash
bash scripts/ops/reset-storage.sh --yes
```
