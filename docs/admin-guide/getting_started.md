# ADE Admin Getting Started Guide

This handbook shows how to run and administer the Automatic Data Extractor (ADE)
without assuming prior context. ADE standardizes on Postgres; for local development
the devcontainer starts a Postgres container and ADE uses that by default.

## 1. What ADE Ships With
- **Storage layout** – documents and runtime artifacts live under `data/`. The
  database itself lives in Postgres; in local dev, the Postgres container
  persists data in a Docker named volume (managed by Compose).
- **FastAPI backend + worker** – the API in
  `apps/ade-api/src/ade_api/main.py` handles requests, while `ade-worker`
  provisions environments and executes runs from the database queue.
- **Frontend SPA** – the React app in `apps/ade-web` runs on the Vite dev server
  in development; in production the built SPA is served by nginx (see
  `apps/ade-web/nginx/default.conf.template`), while the API remains API-only.


## 2. Prerequisites
- **Python 3.14.2+** and **uv** available on your `PATH`. Windows installers live at
  <https://www.python.org/downloads/>. Install uv from <https://astral.sh/uv>.
- **Node.js 20 LTS** (includes `npm`). Download from
  <https://nodejs.org/en/download/>.
- **Git** for cloning and version control – available at
  <https://git-scm.com/downloads>.

Confirm everything is discoverable before continuing:

```bash
python --version
node --version
npm --version
git --version
```

## 3. About `.env` Files
ADE reads configuration from environment variables. During local development you
may keep them in a `.env` file in the project root so FastAPI and Docker
load the same values.

`.env` is optional. If it is missing, ADE uses defaults that target the local
Postgres container (`postgres:5432`, database `ade`, user `ade`). Time-based settings accept
either plain seconds (`900`) or suffixed strings like `15m`, `1h`, or `30d`, so
you can stay consistent whether you configure them via `.env` or export
environment variables in your shell.

## 4. Option A – Develop with the source tree (recommended)

1. Clone the repo and install dependencies:

   ```bash
   git clone https://github.com/clac-ca/automatic-data-extractor.git
   cd automatic-data-extractor
   # uv will create the project venv at .venv automatically.
   # If you want to activate it explicitly:
   # source .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
   ./setup.sh
   ```

   Note: `ade-worker` installs `ade-engine` from the separate engine repo (currently tracking `@main`; tags will follow).
   `setup.sh` runs `uv --project apps/ade-api sync --dev` and `uv --project apps/ade-worker sync --dev` into a shared `.venv`. Use `ade-api` and `ade-worker` CLIs; the web app uses `npm` scripts in `apps/ade-web`.

2. Apply migrations, then start the dev services:

   ```bash
   ade-api migrate
   ade-api dev
   ```

   Ensure Postgres is reachable (local container or external Postgres) and `ADE_DATABASE_URL` is set
   before starting the services.

   In separate terminals, start the worker and web dev server:

   ```bash
   ade-worker start
   npm run dev --prefix apps/ade-web
   ```

   - Dev flow: `ade-api dev` + `ade-worker start` + `npm run dev --prefix apps/ade-web`.
   - Prod-ish flow: `docker compose up -d api worker web`.

3. Confirm the API is healthy:

   ```bash
   curl http://localhost:8000/api/v1/health
   ```

All runtime state stays under `data/` except the Postgres data directory, which is stored in a Docker named volume. Stop the API/worker processes before deleting files and remove only the pieces you need to refresh. For local Postgres dev, remove the Postgres volume after the container stops (for example: `docker volume rm <compose_project>_ade_pg_data`), then re-run `ade-api migrate` before restarting services. Leave `data/workspaces/<workspace_id>/files/` intact unless you intend to delete uploaded sources.

### Run API and web manually (optional)
If you prefer separate terminals, run the API and web servers independently. Install dependencies in `apps/ade-web/` first (repeat only after dependency updates).
If you have not applied migrations yet, run `ade-api migrate` before starting the API.

```bash
# Terminal 1
ade-api dev

# Terminal 2
npm run dev --prefix apps/ade-web

# Terminal 3 (optional)
ade-worker start
```

Tip: If you frequently switch branches, re-run `./setup.sh` after pulling changes so your environment stays in sync with the code.

## 5. Option B – Run ADE with Docker
Docker is useful when you want ADE isolated from the host Python install or to
run it on a server. A published image is available at `ghcr.io/clac-ca/automatic-data-extractor:latest`,
or you can build locally.

### 5.1 Build a local image
```bash
git clone https://github.com/clac-ca/automatic-data-extractor.git
cd automatic-data-extractor
docker build -t ade-app:local .
```

### 5.2 Run the containers (split services)

```bash
docker network create ade-net

docker run --rm --name ade-migrate --network ade-net --env-file .env \
  ade-app:local ade-api migrate

docker run --detach --name ade-api --network ade-net --env-file .env \
  ade-app:local ade-api start

docker run --detach --name ade-worker --network ade-net --env-file .env \
  ade-app:local ade-worker start

docker run --detach --name ade-web --network ade-net -p 8080:8080 \
  -e ADE_WEB_PROXY_TARGET=http://ade-api:8000 \
  ade-app:local /usr/local/bin/ade-web-entrypoint
```

The bind mount keeps documents and runtime artifacts under `./data` so they
survive container restarts. The database itself lives in your Postgres
instance (local container or external Postgres), so ensure `ADE_DATABASE_URL` is set
before startup. Run `ade-api migrate` before starting the API/worker services.
Check health the same way:

```bash
curl http://localhost:8000/api/v1/health
```

To stop and remove the containers:

```bash
docker rm -f ade-api ade-worker ade-web
```

## 6. Where ADE Stores Data
- Postgres data – stored in a Docker named volume for local dev (via the Postgres service).
- `data/workspaces/<workspace_id>/files/` – uploaded source files.
- `data/logs/` *(if enabled)* – structured JSON logs.

Back up the `data/` directory to retain everything you need for a full
restore.

## 7. Roadmap + TODOs
- **TODO:** Publish an official Docker image to GitHub Container Registry and
  reference it in this guide.
- **TODO:** Update the onboarding section once the frontend ships the admin
  walkthrough.
- Consider setting `ADE_SECRET_KEY` to a long random value before going
  beyond local testing.

With these basics you can run ADE on a laptop, VM, or container host and manage
administrators through the API while the frontend experience is completed.

## 8. Troubleshooting
- **`uvicorn` exits immediately:** ensure the Python dependencies are installed (run `./setup.sh`) and that the configured port is free. When using `--reload`, verify the file watcher can spawn a subprocess; otherwise fall back to the default single-process mode (`uvicorn ade_api.main:app`).
- **Port conflicts on 8080:** change the host port mapping in Compose or `docker run -p` for the web container; for API-only runs use `ade-api start --port 9000` or stop the conflicting process.
- **Frontend shows a blank page:** rebuild assets with `npm run build --prefix apps/ade-web` and confirm nginx is serving `/usr/share/nginx/html` and proxying `/api` to the API service.
- **Frontend cannot reach the API:** ensure the backend is accessible at the same origin and that requests target the `/api/v1` prefix.
