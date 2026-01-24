# Production: single ADE image (API + Worker + CLI + Web build)

The production image is built from the root `Dockerfile` and contains:

- `ade-api` package (API)
- `ade-worker` package (worker)
- `ade-cli` package (provides `ade` command)
- built web assets copied to: `/app/apps/ade-web/dist`

## Build the image

```bash
bash scripts/docker/build-image.sh
```

## Run with Compose (prod-like locally)

```bash
cp .env.example .env
ADE_IMAGE=ade-app:local docker compose -f docker-compose.production.yml up
```

This runs:
- API container from the single image
- Worker container from the same single image

You must provide external SQL + Storage (set `ADE_SQL_*` and `ADE_STORAGE_*` in `.env`).

## Run with docker run

API + worker (default `ade start`):

```bash
docker run --rm -p 8000:8000 --env-file .env -e ADE_DATA_DIR=/app/data -v ./data:/app/data ade-app:local
```

API only:

```bash
docker run --rm -p 8000:8000 --env-file .env -e ADE_DATA_DIR=/app/data -v ./data:/app/data ade-app:local api
```

Worker only:

```bash
docker run --rm --env-file .env -e ADE_DATA_DIR=/app/data -v ./data:/app/data ade-app:local worker
```

Init (optional one-time):

```bash
docker run --rm --env-file .env -e ADE_DATA_DIR=/app/data -v ./data:/app/data ade-app:local init
```

## CLI inside the container

You can run commands in a container shell:

```bash
docker run --rm -it --env-file .env -e ADE_DATA_DIR=/app/data -v ./data:/app/data ade-app:local bash
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
