# Automatic Data Extractor (ADE)

[![CI](https://github.com/clac-ca/automatic-data-extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/clac-ca/automatic-data-extractor/actions/workflows/ci.yml)
[![Docker Image (GHCR)](https://github.com/clac-ca/automatic-data-extractor/actions/workflows/docker.yml/badge.svg)](https://github.com/clac-ca/automatic-data-extractor/actions/workflows/docker.yml)
ADE is a multi-app project:

- **ade-api** — HTTP API (FastAPI)
- **ade-worker** — background worker
- **ade-web** — React UI
- **ade-cli** — CLI + container entrypoint

This repository publishes **one Docker image** that contains **api + worker + cli + built web assets**.

## Quickstart (Docker, local)

The easiest “it just works” path is Docker Compose because ADE depends on:
- SQL Server
- Blob storage (Azurite locally, Azure Storage in production)

### One-liner

```bash
curl -LO https://raw.githubusercontent.com/clac-ca/automatic-data-extractor/main/docker-compose.yml \
  && docker compose -f docker-compose.yml up
```

This starts:
- SQL Server (local container)
- Azurite (blob-only)
- ADE (single container by default runs API + worker)

> **Apple Silicon note:** SQL Server Linux containers are x86_64 only today.
> The compose files set `platform: linux/amd64` so the same quickstart works on
> both Intel Linux/Windows and Apple Silicon (via Docker Desktop emulation).

> **Note:** `docker-compose.yml` contains safe **development defaults** (including a default SQL password).
> For anything beyond local evaluation, override values with environment variables or a `.env` file.

### Optional: use a .env file

```bash
curl -LO https://raw.githubusercontent.com/clac-ca/automatic-data-extractor/main/.env.example
cp .env.example .env
docker compose -f docker-compose.yml up
```

## Running the image directly

The image is “CLI-style”:

- `ENTRYPOINT ["ade"]`
- default `CMD ["start"]`

So running without arguments behaves like running `ade start`.

### Start ade-api + ade-web + ade-worker (default)

```bash
docker run --rm -p 8000:8000 ghcr.io/clac-ca/automatic-data-extractor:latest
```

### Start only ade-api + ade-web

```bash
docker run --rm -p 8000:8000 ghcr.io/clac-ca/automatic-data-extractor:latest api
```

### Start only ade-worker

```bash
docker run --rm ghcr.io/clac-ca/automatic-data-extractor:latest worker
```

### What `ade start` does

`ade start` runs an initialization step first:

- Ensures the SQL database named by `ADE_SQL_DATABASE` exists (creates it if missing and credentials allow)
- Ensures storage defaults exist (`ADE_STORAGE_ACCOUNT_NAME`, etc.)
- Starts API and worker together

You can run init explicitly:

```bash
docker run --rm ghcr.io/clac-ca/automatic-data-extractor:latest init
```

## Standard production pattern (recommended)

Even though we publish **one image**, the most common deployment style is still:

- one container running the API
- one container running the worker
- both containers use the **same image**, but different commands

Use `docker-compose.production.yml` as an example:

```bash
ADE_IMAGE=ghcr.io/clac-ca/automatic-data-extractor:latest docker compose -f docker-compose.production.yml up
```

## Configuration (ADE_ env vars)

All ADE configuration uses `ADE_*` variables.

### SQL

- `ADE_SQL_HOST` (default: `sql`)
- `ADE_SQL_PORT` (default: `1433`)
- `ADE_SQL_USER` (default: `sa`)
- `ADE_SQL_PASSWORD` (default: set in compose quickstart)
- `ADE_SQL_DATABASE` (default: `ade`)
- `ADE_SQL_ENCRYPT` (default: `yes`)
- `ADE_SQL_TRUST_SERVER_CERTIFICATE` (default: `yes` for local SQL container)

### Storage (Azure Storage or Azurite)

- `ADE_STORAGE_ACCOUNT_NAME` (default: `devstoreaccount1`)
- `ADE_STORAGE_ACCOUNT_KEY` (default: devstoreaccount1 key for local Azurite)
- `ADE_STORAGE_BLOB_ENDPOINT` (local default: `http://azurite:10000/<account>`)
- `ADE_STORAGE_CONNECTION_STRING` (if set, overrides the pieces above)

## Development (VS Code Devcontainer)

1) Copy env defaults:

```bash
cp .env.example .env
```

2) Open VS Code → **Dev Containers: Reopen in Container**

The devcontainer runs:

```bash
bash scripts/dev/setup.sh
```

This installs:

- Python deps for `ade-api`, `ade-worker`, and `ade-cli` via uv (workspace sync)
- Node deps for `ade-web` (via your lockfile)

3) Run everything:

```bash
ade dev
```

If you **don't** need the React app, you can skip Node/web setup:

```bash
bash scripts/dev/setup.sh --no-web
```

## Build the production image locally

```bash
ADE_IMAGE=ade-app:local bash scripts/docker/build.sh
```

Then:

```bash
docker run --rm -p 8000:8000 ade-app:local
```

---

## CI, GHCR publishing, and releases

This repo is set up as a “first-class” container project:

- **CI** runs on every PR and on pushes to `main` (`.github/workflows/ci.yml`).
- **Docker images** are built with BuildKit and published to **GitHub Container Registry (GHCR)** (`.github/workflows/docker.yml`).
- **GitHub Releases** are created automatically on version tags (`.github/workflows/release.yml`).

### Image name

By default, images are published as:

- `ghcr.io/clac-ca/automatic-data-extractor`

### Tagging strategy

Standard, predictable tags:

- On `main` pushes:
  - `main`
  - `sha-<shortsha>`
- On version tags (e.g. `v1.2.3`):
  - `1.2.3`
  - `1.2`
  - `1`
  - `latest`

### Releasing

Create and push a `vX.Y.Z` tag to cut a release; GitHub Actions will publish the GHCR image and create a GitHub Release.

See `docs/releasing.md` for the full workflow.

## Why this design is “standard”

This repo follows common Docker UX patterns:

- **Command-driven roles** (pass a subcommand to run worker vs api) — used by images like Vault and Sentry.
- **ENTRYPOINT + CMD** pattern so `docker run image` “just works” and `docker run image <cmd>` overrides behavior.
- **Compose quickstart** published as a single file fetched by `curl`, like Airflow’s official docs.

See docs links in `docs/` (and in the work package).
