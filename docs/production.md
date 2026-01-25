# Production: single ADE image (API + Worker + CLI + Web build)

The production image is built from the root `Dockerfile` and contains:

- `ade-api` package (API)
- `ade-worker` package (worker)
- `ade-cli` package (provides `ade` command)
- built web assets copied to: `/app/apps/ade-web/dist`

## Build the image

```bash
ade docker build
```

## Run with Compose (prod-like locally)

```bash
cp .env.example .env
ADE_IMAGE=ade-app:local docker compose -f docker-compose.production.yml up
```

This runs:
- API container from the single image
- Worker container from the same single image

You must provide external Postgres + Storage (set `ADE_DATABASE_URL`, `ADE_DATABASE_AUTH_MODE`,
`ADE_STORAGE_CONNECTION_STRING`, and optional `ADE_STORAGE_AUTH_MODE=key` in `.env`).
Ensure the database named in `ADE_DATABASE_URL` already exists before starting the containers.

## Run with docker run

API + worker (default `ade start`):

```bash
ade docker run
```

API only:

```bash
ade docker api
```

Worker only:

```bash
ade docker worker
```

## CLI inside the container

You can run commands in a container shell:

```bash
ade docker shell
ade --help
```

## Serving the React frontend in production

This image includes the built `ade-web` output in `/app/apps/ade-web/dist`.
The most “single-image” approach is to have the API serve it as static files.

Example FastAPI snippet:

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/", StaticFiles(directory="apps/ade-web/dist", html=True), name="web")
```
