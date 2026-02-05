# Automatic Data Extractor (ADE)

Self-hostable document extraction service with an **API**, **Web UI**, and background **worker**.

- Local dev: runs with **Docker Compose** (includes local Postgres + Azurite).
- Production: uses **external Postgres** + **external Azure Blob Storage**.

---

## Table of contents

- [Quickstart (local)](#quickstart-local)
- [Production deployment](#production-deployment)
- [Configuration](#configuration)
- [Development (Dev Container)](#development-dev-container)
- [Operations](#operations)
- [Troubleshooting](#troubleshooting)
- [Docs](#docs)

---

## Quickstart (local)

### Requirements
- Docker (with Docker Compose)
- Git

### Run

```bash
git clone https://github.com/clac-ca/automatic-data-extractor
cd automatic-data-extractor
docker compose up --build -d
```

Optional: copy `.env.example` to `.env` only when you want to override defaults.
Local compose defaults set `ADE_AUTH_DISABLED=true` for fastest startup.

Open:

* [http://localhost:8000](http://localhost:8000)

Stop:

```bash
docker compose down
```

Reset local data (database + storage + ADE data):

```bash
docker compose down -v
```

---

## Production deployment

Production uses external services:

* **Postgres**
* **Azure Blob Storage**

`docker-compose.prod.yaml` is optimized for the common case: one `app` container running `api + worker + web`.

```bash
docker compose -f docker-compose.prod.yaml up -d

# Scale-out alternative (app + worker split)
docker compose -f docker-compose.prod.split.yaml up -d
docker compose -f docker-compose.prod.split.yaml up -d --scale worker=3

# Optional: choose published image tag for this deploy command (default is main)
ADE_DOCKER_TAG=development docker compose -f docker-compose.prod.yaml up -d
```

`ADE_DOCKER_TAG` is compose-only (image selection), not ADE runtime config.
Keep runtime settings in `.env`; set tag overrides in shell/CI per deploy command.
Changing tags takes effect only when containers are recreated (and typically after `docker compose pull`).

Scaling guidance (start simple, then split):

- In single-container mode, first tune in-container concurrency:
  - `ADE_WORKER_CONCURRENCY` = max concurrent run slots per container (default `2`)
  - `ADE_API_WORKERS` = API process count per container (default `1`)
- If queue latency is still high or you need better fault isolation, move to split mode and scale `worker` containers.
- In split mode, keep `ADE_WORKER_CONCURRENCY` moderate (for example `2`-`4`) and scale container count with `--scale worker=N`.

Examples:

```bash
# Single-container tuning
ADE_WORKER_CONCURRENCY=4 ADE_API_WORKERS=2 \
docker compose -f docker-compose.prod.yaml up -d

# Split deployment + horizontal worker scaling
ADE_WORKER_CONCURRENCY=2 \
docker compose -f docker-compose.prod.split.yaml up -d --scale worker=3
```

---

## Configuration

Create a `.env` file **next to the compose file you run** when you need to override ADE runtime settings.
The compose examples in this repo read `.env` for interpolation and pass it to ADE containers at runtime.
Use shell/CI overrides for compose-only controls (for example `ADE_DOCKER_TAG`) instead of storing them in `.env`.
Local dependency variables (`POSTGRES_*`, `AZURITE_ACCOUNTS`) are also compose-only and not ADE runtime config.

### Minimum required (example)

```env
# Database (external)
ADE_DATABASE_URL=postgresql+psycopg://user:pass@pg.example.com:5432/ade?sslmode=verify-full

# Public web URL (required in production compose)
ADE_PUBLIC_WEB_URL=https://ade.example.com

# Azure Blob (set exactly one auth method; do not set both)
# ADE_BLOB_ACCOUNT_URL=https://<account>.blob.core.windows.net
# ADE_BLOB_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net
ADE_BLOB_CONTAINER=ade

# App secret (required)
ADE_SECRET_KEY=<long-random-secret>
```

See `.env.example` for the full set of supported environment variables.

### Service selection (optional)

To run only a subset of in-container services:

```bash
ADE_SERVICES=api,web docker compose up -d app
```

---

## Development (Dev Container)

Fastest contributor setup:

1. Install Docker + VS Code + Dev Containers extension
2. Open the repo in VS Code
3. Run **“Dev Containers: Reopen in Container”**

Note: nginx config is rendered when the container starts from the template baked into the image. If you change nginx templates or need a different `ADE_INTERNAL_API_URL` for nginx, rebuild or restart the container.

---

## Operations

### View logs

```bash
docker compose logs -f
```

### Start fresh

```bash
docker compose down -v
```

---

## Troubleshooting

* Check logs:

  * `docker compose logs -f`
* Full reset:

  * `docker compose down -v`

---

## Docs

Full documentation lives in `docs/index.md`.

## Contributing

PRs welcome. If you’re making a change, please include:

* What changed
* How to run/test it locally

---

## Security

* Treat `ADE_SECRET_KEY` like a password.
* For production, run behind HTTPS and restrict network access to Postgres/Blob where possible.

---

## License
 
The MIT License (MIT)

Copyright (c) 2015 Chris Kibble

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
