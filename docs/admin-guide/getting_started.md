# ADE Admin Getting Started Guide

This handbook shows how to run and administer the Automatic Data Extractor (ADE)
without assuming prior context. ADE standardizes on SQL Server/Azure SQL; for
local development the devcontainer starts a SQL Server container and ADE uses
that by default.

## 1. What ADE Ships With
- **Storage layout** – documents and runtime artifacts live under `data/`. The
  database itself lives in SQL Server/Azure SQL; in local dev, the SQL container
  persists data under `data/sql`.
- **FastAPI backend + worker** – the API in
  `apps/ade-api/src/ade_api/main.py` handles requests, while `ade-worker`
  provisions environments and executes runs from the database queue.
- **Frontend SPA** – the React app in `apps/ade-web` runs on the Vite dev server
  in development; in production you can serve the built `apps/ade-web/dist`
  bundle via the API container (`ade start`) or behind a reverse proxy.


## 2. Prerequisites
- **Python 3.12+** with `pip` available on your `PATH`. Windows installers live at
  <https://www.python.org/downloads/>.
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
SQL container (`sql:1433`, database `ade`, user `sa`). Time-based settings accept
either plain seconds (`900`) or suffixed strings like `15m`, `1h`, or `30d`, so
you can stay consistent whether you configure them via `.env` or export
environment variables in your shell.

## 4. Option A – Develop with the source tree (recommended)

1. Clone the repo and install dependencies:

   ```bash
   git clone https://github.com/your-org/automatic-data-extractor.git
   cd automatic-data-extractor
   python3 -m venv .venv
   source .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1

   python -m pip install --upgrade pip
   pip install --no-cache-dir -e apps/ade-cli -e apps/ade-api -e apps/ade-worker

   cd apps/ade-web
   npm install
   cd ..
   ```

   Note: `ade-worker` installs `ade-engine` from the separate engine repo (currently tracking `@main`; tags will follow).

2. Start the dev services (this runs migrations first):

   ```bash
   ade dev
   ```

   Ensure SQL Server is reachable (local container or Azure SQL) and `ADE_SQL_*` is set
   before starting the services.

   Use `ade dev` for the standard dev loop (runs migrations, then API reload + Vite hot module reload + worker). If you only want one component, use `ade dev --api`, `ade dev --web`, or `ade dev --worker`. Use `--no-worker` if you want to skip background jobs while still running API + web.
   - Dev flow: `ade dev` (runs migrations, then API + worker + Vite dev server).
   - Prod-ish flow: `ade start` (API role by default; set `ADE_ROLE=worker` for worker).

3. Confirm the API is healthy:

   ```bash
   curl http://localhost:8000/health
   ```

All runtime state stays under `data/`. Stop the API/worker processes before deleting files and remove only the pieces you need to refresh. For local SQL dev, deleting `data/sql/` after the SQL container stops resets the database; `ade dev`/`ade start` (API role) will re-run migrations on the next launch (or run `ade migrate` manually if you prefer). Leave `data/workspaces/<workspace_id>/documents/` intact unless you intend to delete uploaded sources.

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

Tip: If you frequently switch branches, re-run the editable installs (`pip install -e apps/ade-cli -e apps/ade-api -e apps/ade-worker`) in your virtualenv (and `npm install` in `apps/ade-web`) after pulling changes so your environment stays in sync with the code.

## 5. Option B – Run ADE with Docker
Docker is useful when you want ADE isolated from the host Python install or to
run it on a server. An official image will be published to GitHub Container
Registry soon.

> **TODO:** Replace the build step below with a `docker pull` command once the
> image is published.

### 5.1 Build a local image
```bash
git clone https://github.com/your-org/automatic-data-extractor.git
cd automatic-data-extractor
IMAGE_TAG=ade-app:local bash scripts/docker/build.sh
```

### 5.2 Run the container
```bash
mkdir -p data
docker run -d --name ade -p 8000:8000 -v "$(pwd)/data:/app/data" ade-app:local
```

To run the worker from the same image:

```bash
docker run -d --name ade-worker --env-file .env -e ADE_ROLE=worker ade-app:local
```

The volume keeps documents and runtime artifacts on the host so they
survive container restarts. The database itself lives in your SQL Server
instance (local container or Azure SQL), so ensure `ADE_SQL_*` is set
before startup. The API container runs migrations on startup via `ade start`.
Check health the same way:

```bash
curl http://localhost:8000/health
```

To stop and remove the container:

```bash
docker rm -f ade
```

## 6. Where ADE Stores Data
- `data/sql/` – persisted SQL Server data for local dev (via the devcontainer SQL service).
- `data/workspaces/<workspace_id>/documents/` – uploaded source files.
- `data/logs/` *(if enabled)* – structured JSON logs.

Back up the `data/` directory to retain everything you need for a full
restore.

## 7. Roadmap + TODOs
- **TODO:** Publish an official Docker image to GitHub Container Registry and
  reference it in this guide.
- **TODO:** Update the onboarding section once the frontend ships the admin
  walkthrough.
- Consider setting `ADE_JWT_SECRET` to a long random value before going
  beyond local testing.

With these basics you can run ADE on a laptop, VM, or container host and manage
administrators through the API while the frontend experience is completed.

## 8. Troubleshooting
- **`uvicorn` exits immediately:** ensure the Python dependencies are installed (`pip install -e apps/ade-cli -e apps/ade-api -e apps/ade-worker`) and that the configured port is free. When using `--reload`, verify the file watcher can spawn a subprocess; otherwise fall back to the default single-process mode (`uvicorn ade_api.main:create_app --factory`).
- **Port conflicts on 8000:** choose another port with `uvicorn ... --port 9000` or stop the conflicting process.
- **Frontend shows a blank page:** rebuild assets with `ade build` (or `npm run build` in `apps/ade-web/`) and confirm your web server is serving `apps/ade-web/dist/` and forwarding `/api/v1` to the API.
- **Frontend cannot reach the API:** ensure the backend is accessible at the same origin and that requests target the `/api/v1` prefix.
