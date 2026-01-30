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
  in development; in production the image ships with the built bundle in
  `/app/web/dist` and sets `ADE_FRONTEND_DIST_DIR` so the API can serve it
  (`ade api start` or `ade start`) or you can serve it behind a reverse proxy.


## 2. Prerequisites
- **Python 3.12+** and **uv** available on your `PATH`. Windows installers live at
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
   # Optional: create/activate a venv first if you want isolation.
   # python -m venv .venv
   # source .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
   ./setup.sh
   ```

   Note: `ade-worker` installs `ade-engine` from the separate engine repo (currently tracking `@main`; tags will follow).

2. Start the dev services (this runs migrations first):

   ```bash
   ade dev
   ```

   Ensure Postgres is reachable (local container or external Postgres) and `ADE_DATABASE_URL` is set
   before starting the services.

   Use `ade dev` for the standard dev loop (runs migrations, then API reload + Vite hot module reload + worker). If you only want one component, use `ade dev --api`, `ade dev --web`, or `ade dev --worker`. Use `--no-worker` if you want to skip background jobs while still running API + web.
   - Dev flow: `ade dev` (runs migrations, then API + worker + Vite dev server).
   - Prod-ish flow: `ade build` then `ade start` (API + worker, serves built web) or `ade api start` / `ade worker start` for split containers.

3. Confirm the API is healthy:

   ```bash
   curl http://localhost:8000/health
   ```

All runtime state stays under `data/` except the Postgres data directory, which is stored in a Docker named volume. Stop the API/worker processes before deleting files and remove only the pieces you need to refresh. For local Postgres dev, remove the Postgres volume after the container stops (for example: `docker volume rm <compose_project>_ade_pg_data`), then `ade dev`, `ade start`, or `ade api start` will re-run migrations on the next launch (or run `ade api migrate` manually if you prefer). Leave `data/workspaces/<workspace_id>/files/` intact unless you intend to delete uploaded sources.

### Run API and web manually (optional)
If you prefer separate terminals, run the API and web servers independently. Install dependencies in `apps/ade-web/` first (repeat only after dependency updates).

```bash
# Terminal 1
ade dev --api

# Terminal 2
ade dev --web

# Terminal 3 (optional)
ade dev --worker
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
ade docker build
```

### 5.2 Run the container
```bash
ade docker run --detach --name ade --no-rm
```

To run the worker from the same image:

```bash
ade docker worker --detach --name ade-worker --no-rm
```

The bind mount keeps documents and runtime artifacts under `./data` so they
survive container restarts. The database itself lives in your Postgres
instance (local container or external Postgres), so ensure `ADE_DATABASE_URL` is set
before startup. The API container runs migrations on startup via `ade start` (or `ade api start`).
Check health the same way:

```bash
curl http://localhost:8000/health
```

To stop and remove the container:

```bash
docker rm -f ade
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
- **Port conflicts on 8000:** choose another port with `uvicorn ... --port 9000` or stop the conflicting process.
- **Frontend shows a blank page:** rebuild assets with `ade build` (or `npm run build` in `apps/ade-web/`) and confirm `ADE_FRONTEND_DIST_DIR` points to the built assets (in the container image this is `/app/web/dist`) and that `/api/v1` is routed to the API.
- **Frontend cannot reach the API:** ensure the backend is accessible at the same origin and that requests target the `/api/v1` prefix.
