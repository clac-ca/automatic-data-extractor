# ADE Admin Getting Started Guide

This handbook shows how to run and administer the Automatic Data Extractor (ADE)
without assuming prior context. ADE is designed to be a small, self-contained
service that relies on a bundled SQLite database, so you can evaluate it
anywhere without provisioning external infrastructure.

## 1. What ADE Ships With
- **Self-contained storage** – ADE persists all metadata in
  `data/db/api.sqlite`. Documents and other artefacts live alongside it
  under `data/`. No external database service is required.
- **Deterministic FastAPI backend** – requests are handled by the factory in
  `apps/ade-api/src/ade_api/main.py`. Background work stays inside the same process.
- **(TODO)** The forthcoming frontend will guide first-time administrators
  through setup. Until it lands, rely on the API reference and the docs
  included in this guide.


## 2. Prerequisites
- **Python 3.11+** with `pip` available on your `PATH`. Windows installers live at
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
ADE reads configuration from environment variables. During local development we
keep them in a `.env` file in the project root so FastAPI and Docker
all load the same values.

An example file is included. Copy it and adjust the values you need:

```bash
cp .env.example .env
# edit .env to set secrets before starting ADE
```

If you delete `.env`, ADE falls back to its defaults (SQLite in
`data/db`, docs disabled outside `local`, etc.). Time-based settings
accept either plain seconds (`900`) or suffixed strings like `15m`, `1h`, or
`30d`, so you can stay consistent whether you configure them via `.env` or
export environment variables in your shell.

## 4. Option A – Develop with the source tree (recommended)

1. Clone the repo and install dependencies:

   ```bash
   git clone https://github.com/your-org/automatic-data-extractor.git
   cd automatic-data-extractor
   cp .env.example .env

   python3 -m venv .venv
   source .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1

   python -m pip install --upgrade pip
   pip install --no-cache-dir -e apps/ade-cli -e apps/ade-engine -e apps/ade-api

   cd apps/ade-web
   npm install
   cd ..
   ```

2. Start the application server:

   ```bash
   ade dev --backend --no-frontend
   ```

   The FastAPI factory performs an idempotent bootstrap before serving requests:

   - create the SQLite directory (`data/db/`) and its parents if they are missing,
   - run Alembic migrations in order, logging progress to the console, and
   - print a summary of the resolved settings (sourced from `.env` and the environment).

   With autoreload, uvicorn watches the repository for changes while still serving the compiled SPA from `apps/ade-api/src/ade_api/web/static/`, so <http://localhost:8000/> delivers both the UI and API. Omit autoreload by running `ade start`. When you need fresh frontend assets, run `ade build` from the repository root; the build step compiles the React app and copies the output into `apps/ade-api/src/ade_api/web/static/`.
   - Dev flow: `ade dev` (backend autoreload + Vite dev server; no frontend build required).
   - Prod-ish flow: `ade build` (produces static assets) then `ade start` (serves backend + built SPA). If `ade start` returns `{"detail":"SPA build not found"}`, you skipped `ade build`.

3. Confirm the API is healthy:

   ```bash
   curl http://localhost:8000/health
   ```

All runtime state stays under `data/`. Stop the FastAPI process before deleting files and remove only the pieces you need to refresh. Deleting `data/db/` after the app stops resets the SQLite database; the next bootstrap recreates the directory and reapplies migrations automatically. Leave `data/workspaces/<workspace_id>/documents/` intact unless you intend to delete uploaded sources.

### Run backend and frontend manually (optional)
The uvicorn command above serves the prebuilt SPA. For frontend development with hot module reload, run the backend and the Vite dev server in separate terminals. Install dependencies in `apps/ade-web/` first (repeat only after dependency updates).

```bash
# Terminal 1
ade dev --backend --no-frontend

# Terminal 2
ade dev --frontend --no-backend
```

Tip: If you frequently switch branches, re-run the editable installs (`pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`) in your virtualenv (and `npm install` in `apps/ade-web`) after pulling changes so your environment stays in sync with the code.

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
cp .env.example .env
docker build -t ade:local .
# or use the helper script
# ade docker:build
```

### 5.2 Run the container
```bash
docker run -d --name ade-backend \
  --env-file .env \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  ade:local
# or run interactively with
# ade docker:up --detach
```

The bind mount keeps the SQLite database and documents on the host so they
survive container restarts. Check health the same way:

```bash
curl http://localhost:8000/health
```

The bundled FastAPI server serves both the API and the compiled React frontend from the same container, so reverse proxies only need to forward requests to port 8000.

When you deploy the frontend in production, compile it once (`ade build` or `npm run build` in `apps/ade-web/`, then copy `apps/ade-web/dist/` into `apps/ade-api/src/ade_api/web/static/`). FastAPI serves those files directly, so your reverse proxy only needs to forward requests to the backend.

To stop and remove the container:

```bash
docker stop ade-backend
docker rm ade-backend
```

## 6. Where ADE Stores Data
- `data/db/api.sqlite` – primary metadata database (SQLite).
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
- **`uvicorn` exits immediately:** ensure the Python dependencies are installed (`pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api`) and that the configured port is free. When using `--reload`, verify the file watcher can spawn a subprocess; otherwise fall back to the default single-process mode (`uvicorn ade_api.main:create_app --factory`).
- **Port conflicts on 8000:** choose another port with `uvicorn ... --port 9000` or stop the conflicting process.
- **Frontend shows a blank page:** rebuild assets with `ade build` (or `npm run build` in `apps/ade-web/`) and copy `apps/ade-web/dist/` into `apps/ade-api/src/ade_api/web/static/`).
- **Frontend cannot reach the API:** ensure the backend is accessible at the same origin and that requests target the `/api` prefix.
