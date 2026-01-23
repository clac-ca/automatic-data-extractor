# Production: single ADE image (API + Worker + CLI + Web build)

The production image is built from the root `Dockerfile` and contains:

- `ade-api` package (API)
- `ade-worker` package (worker)
- `ade-cli` package (provides `ade` command)
- built web assets copied to: `/app/apps/ade-web/dist`

## Build the image

```bash
IMAGE_TAG=ade-app:local bash scripts/docker/build.sh
```

## Run with Compose (prod-like locally)

```bash
cp .env.example .env
IMAGE_TAG=ade-app:local docker compose -f compose.prod.yaml up
```

This runs:
- SQL + Azurite locally (dev-only)
- API container from the single image
- Worker container from the same single image

## Run with docker run

API (default role is api):

```bash
docker run --rm -p 8000:8000 --env-file .env ade-app:local
```

Worker:

```bash
docker run --rm --env-file .env -e ADE_ROLE=worker ade-app:local
```

## CLI inside the container

You can run commands in a container shell:

```bash
docker run --rm -it --env-file .env ade-app:local bash
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
