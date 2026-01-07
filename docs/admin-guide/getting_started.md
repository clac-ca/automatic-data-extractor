# ADE Admin Getting Started Guide

This handbook shows how to run and administer the Automatic Data Extractor (ADE)
without assuming prior context. ADE is designed to be a small, self-contained
service that relies on a bundled SQLite database, so you can evaluate it
anywhere without provisioning external infrastructure.

## 1. What ADE Ships With
- **Self-contained storage** – ADE persists all metadata in
  `data/db/ade.sqlite`. Documents and other artefacts live alongside it
  under `data/`. No external database service is required.
- **FastAPI backend + worker** – the API in
  `apps/ade-api/src/ade_api/main.py` handles requests, while `ade-worker`
  provisions environments and executes runs from the database queue.
- **Frontend SPA** – the React app in `apps/ade-web` runs on the Vite dev server
  in development; in production you can serve the built `apps/ade-web/dist`
  bundle via `ade start` or behind a reverse proxy.


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
   pip install --no-cache-dir -e apps/ade-cli -e apps/ade-engine -e apps/ade-api -e apps/ade-worker

   cd apps/ade-web
   npm install
   cd ..
   ```

2. Start the dev services (this runs migrations first):

   ```bash
   ade dev
   ```

   Use `ade dev` for the standard dev loop (runs migrations, then API reload + Vite hot module reload + worker). If you only want the API, run `ade dev --api --no-web --no-worker` (or `ade dev --api-only`). If you only want the web server, run `ade dev --web --no-api`. Use `--no-worker` if you want to skip background jobs.
   - Dev flow: `ade dev` (runs migrations, then API + worker + Vite dev server).
   - Prod-ish flow: `ade start` (builds frontend if missing, serves frontend + API + worker; runs migrations first).

3. Confirm the API is healthy:

   ```bash
   curl http://localhost:8000/health
   ```

All runtime state stays under `data/`. Stop the API/worker processes before deleting files and remove only the pieces you need to refresh. Deleting `data/db/` after the services stop resets the SQLite database; `ade dev`/`ade start` will re-run migrations on the next launch (or run `ade migrate` manually if you prefer). Leave `data/workspaces/<workspace_id>/documents/` intact unless you intend to delete uploaded sources.

### Run API and web manually (optional)
If you prefer separate terminals, run the API and web servers independently. Install dependencies in `apps/ade-web/` first (repeat only after dependency updates).

```bash
# Terminal 1
ade dev --api --no-web --no-worker

# Terminal 2
ade dev --web --no-api

# Terminal 3 (optional)
ade worker
```

Tip: If you frequently switch branches, re-run the editable installs (`pip install -e apps/ade-cli -e apps/ade-engine -e apps/ade-api -e apps/ade-worker`) in your virtualenv (and `npm install` in `apps/ade-web`) after pulling changes so your environment stays in sync with the code.

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
docker compose up --build
```

### 5.2 Run the stack
```bash
docker compose up -d
```

The volume keeps the SQLite database and documents on the host so they
survive container restarts. The API container runs migrations on startup
via `ade start --no-worker --no-web`. Check health the same way:

```bash
curl http://localhost:8000/health
```

The web server (nginx) serves the compiled React frontend and proxies `/api/v1` to the FastAPI service.

When you deploy the frontend in production, compile it once (`ade build` or `npm run build` in `apps/ade-web/`) and serve `apps/ade-web/dist/` from your web server or reverse proxy. Configure the reverse proxy to forward `/api/v1` requests to the FastAPI service.

To stop and remove the stack:

```bash
docker compose down
```

## 6. Where ADE Stores Data
- `data/db/ade.sqlite` – primary metadata database (SQLite).
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
- **Frontend shows a blank page:** rebuild assets with `ade build` (or `npm run build` in `apps/ade-web/`) and confirm your web server is serving `apps/ade-web/dist/` and forwarding `/api/v1` to the API.
- **Frontend cannot reach the API:** ensure the backend is accessible at the same origin and that requests target the `/api/v1` prefix.
