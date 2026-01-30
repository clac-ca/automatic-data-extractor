# Automatic Data Extractor (ADE)

[![CI](https://github.com/clac-ca/automatic-data-extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/clac-ca/automatic-data-extractor/actions/workflows/ci.yml)
[![Docker Image (GHCR)](https://github.com/clac-ca/automatic-data-extractor/actions/workflows/docker.yml/badge.svg)](https://github.com/clac-ca/automatic-data-extractor/actions/workflows/docker.yml)
ADE is a multi-app project:

- **ade-api** — HTTP API (FastAPI)
- **ade-worker** — background worker (event-driven via Postgres NOTIFY/LISTEN)
- **ade-web** — React UI
- **ade-cli** — CLI + container entrypoint

This repository publishes **one Docker image** that contains **api + worker + cli + built web assets**.

## Quickstart (Docker, local)

The easiest “it just works” path is Docker Compose because ADE depends on:
- Postgres
- Blob storage (Azurite locally, Azure Storage in production)

### One-liner

```bash
curl -LO https://raw.githubusercontent.com/clac-ca/automatic-data-extractor/main/docker-compose.yml \
  && docker compose -f docker-compose.yml up
```

This starts:
- Postgres (local container)
- Azurite (blob-only)
- ADE (single container by default runs API + worker)

> **Note:** `docker-compose.yml` contains safe **development defaults** (including a default Postgres password).
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
docker run --rm -p 8000:8000 --env-file .env -e ADE_DATA_DIR=/app/data -v ./data:/app/data ghcr.io/clac-ca/automatic-data-extractor:latest
```

### Start only ade-api + ade-web

```bash
docker run --rm -p 8000:8000 --env-file .env -e ADE_DATA_DIR=/app/data -v ./data:/app/data ghcr.io/clac-ca/automatic-data-extractor:latest api start
```

### Start only ade-worker

```bash
docker run --rm --env-file .env -e ADE_DATA_DIR=/app/data -v ./data:/app/data ghcr.io/clac-ca/automatic-data-extractor:latest worker start
```

### What `ade start` does

`ade start` runs:

- Migrations
- API and worker together
- Serves the built frontend when `apps/ade-web/dist` is present (run `ade build` if you're starting from source)

Ensure the database named in `ADE_DATABASE_URL` already exists (for compose, this is handled by `POSTGRES_DB`).

## Standard production pattern (recommended)

Even though we publish **one image**, the most common deployment style is still:

- one container running the API
- one container running the worker
- both containers use the **same image**, but different commands

Use `docker-compose.prod.yml` for single-container BYO services, or `docker-compose.prod.split.yml` for split API + worker:

```bash
ADE_IMAGE=ghcr.io/clac-ca/automatic-data-extractor:latest docker compose -f docker-compose.prod.yml up
# or
ADE_IMAGE=ghcr.io/clac-ca/automatic-data-extractor:latest docker compose -f docker-compose.prod.split.yml up
```

## Configuration (ADE_ env vars)

All ADE configuration uses `ADE_*` variables.

### Database (Postgres)

- `ADE_DATABASE_URL` (canonical SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host:5432/db?sslmode=disable`)
- `ADE_DATABASE_AUTH_MODE` (`password` or `managed_identity`)
- `ADE_DATABASE_SSLROOTCERT` (optional CA path for verify-full)

### Storage (Azure Blob)

- `ADE_BLOB_CONTAINER` (required, private container)
- `ADE_BLOB_ACCOUNT_URL` (managed identity / AAD, e.g. `https://<account>.blob.core.windows.net`)
- `ADE_BLOB_CONNECTION_STRING` (connection string for Azurite or shared-key auth)
- `ADE_BLOB_PREFIX` (optional; defaults to `workspaces`)

Auth is inferred: if `ADE_BLOB_CONNECTION_STRING` is set, it is used; otherwise
`ADE_BLOB_ACCOUNT_URL` is required and ADE uses `DefaultAzureCredential`.

`ADE_DATABASE_URL`, `ADE_BLOB_CONTAINER`, and one of `ADE_BLOB_ACCOUNT_URL` or
`ADE_BLOB_CONNECTION_STRING` are required in all environments.

## Development (VS Code Devcontainer)

1) Copy env defaults:

```bash
cp .env.example .env
```

2) Open VS Code → **Dev Containers: Reopen in Container**

The devcontainer runs:

```bash
./setup.sh
```

This installs:

- Python deps for `ade-api`, `ade-worker`, and `ade-cli` via uv (workspace sync)
- Node deps for `ade-web` (via your lockfile)

3) Run everything:

```bash
ade dev
```

## Build the production image locally

```bash
ade docker build
```

Then:

```bash
ade docker run
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
