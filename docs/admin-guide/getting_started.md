# ADE Admin Getting Started Guide

This handbook shows how to run and administer the Automatic Data Extractor (ADE)
without assuming prior context. ADE is designed to be a small, self-contained
service that relies on a bundled SQLite database, so you can evaluate it
anywhere without provisioning external infrastructure.

## 1. What ADE Ships With
- **Self-contained storage** – ADE persists all metadata in
  `backend/data/db/ade.sqlite`. Documents and other artefacts live alongside it
  under `backend/data/`. No external database service is required.
- **Deterministic FastAPI backend** – requests are handled by the app in
  `backend/api/main.py`. Background work stays inside the same process.
- **Admin CLI** – the `ade` command lets you manage users and API keys from any
  terminal that can read the project’s environment.
- **(TODO)** The forthcoming frontend will guide first-time administrators
  through setup. Until it lands, use the CLI steps below.


## 2. Prerequisites
- **Python 3.11** with `pip` available on your `PATH`. Windows installers live at
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
keep them in a `.env` file in the project root so FastAPI, the CLI, and Docker
all load the same values.

An example file is included. Copy it and adjust the values you need:

```bash
cp .env.example .env
# edit .env to set secrets before starting ADE
```

If you delete `.env`, ADE falls back to its defaults (SQLite in
`backend/data/db`, docs disabled outside `local`, etc.).

## 4. Option A – Develop with the source tree (recommended)

1. Clone the repo and install dependencies:

   ```bash
   git clone https://github.com/your-org/automatic-data-extractor.git
   cd automatic-data-extractor
   cp .env.example .env

   python3.11 -m venv .venv
   source .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1

   python -m pip install --upgrade pip
   pip install -e .[dev]
   ```

2. Launch both servers:

   ```bash
   ade start
   ```

   The CLI prints a banner with service URLs, then streams colour-coded logs from FastAPI and Vite. Stop with `Ctrl+C`. Flags such as `--skip-frontend`, `--skip-backend`, `--vite-api-url`, and `--no-color` help in custom setups. The first run automatically executes `npm install`, so dependencies are ready before Vite starts. Open <http://localhost:5173> for the frontend and <http://localhost:8000/docs> for the interactive API docs.

3. Confirm the API is healthy:

   ```bash
   curl http://127.0.0.1:8000/health
   ```

All runtime state stays under `backend/data/`. Remove that directory to reset ADE to a clean slate (for example, between demos).

### Run backend and frontend manually (optional)
Run `npm install` inside `frontend/` before starting the Vite dev server manually (repeat only after dependency updates).

```bash
# Terminal 1
uvicorn backend.api.main:app --reload

# Terminal 2
cd frontend
npm install  # first run only
npm run dev -- --host
```

Tip: If you frequently switch branches, run `pip install -e .[dev]` again after pulling changes so your environment stays in sync with the code.

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
docker build -t ade-backend:local -f docker/backend/Dockerfile .
```

### 5.2 Run the container
```bash
docker run -d --name ade-backend \
  --env-file .env \
  -p 8000:8000 \
  -v "$(pwd)/backend/data:/app/backend/data" \
  ade-backend:local \
  uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

The bind mount keeps the SQLite database and documents on the host so they
survive container restarts. Check health the same way:

```bash
curl http://127.0.0.1:8000/health
```

When you deploy the frontend in production, compile it once (`npm run build`)
and serve the resulting `frontend/dist/` assets from your reverse proxy or
static site host. Point the frontend at the backend URL with the `VITE_API_URL`
environment variable before building.

To stop and remove the container:

```bash
docker stop ade-backend
docker rm ade-backend
```

## 6. Option C – Install a published wheel (evaluation only)
If you only need the administrative CLI and API without editing source, install
ADE from the package index. This flow assumes a wheel has been published.

```bash
python -m pip install automatic-data-extractor
ade --help
```

The wheel ships the CLI and backend code. To run `ade start`, clone the
repository (or download the matching release tarball) so the frontend assets and
example configuration are available locally, then execute `ade start` from that
directory.

## 7. Managing ADE with the CLI
The CLI uses the same settings as the API. It works even when the API is not
running, as long as the `.env` file (or equivalent environment variables) is
accessible.

From a virtual environment or any Python install where ADE is installed:

```bash
# Create the first administrator account
ade users create --email admin@example.com --password "TempPass123!" --role admin

# List existing users (JSON output is handy for scripts)
ade users list --json

# Reset a password without touching the database manually
ade users set-password --email admin@example.com --password-file ~/.secrets/new-password.txt

# Issue and revoke API keys for service automation
ade api-keys issue --email service@example.com --expires-in 30 --json
ade api-keys revoke 01KZYXWVUTSRQPONML
```

When ADE runs in Docker, execute the same commands inside the container so they
share configuration:

```bash
docker exec -it ade-backend ade users create --email admin@example.com --password "TempPass123!" --role admin
```

> **Tip:** Because the CLI talks directly to the SQLite database, avoid running
> long CLI operations while ADE is actively processing heavy requests to keep
> contention low.

## 8. Where ADE Stores Data
- `backend/data/db/ade.sqlite` – primary metadata database (SQLite).
- `backend/data/documents/` – uploaded source files.
- `backend/data/logs/` *(if enabled)* – structured JSON logs.

Back up the `backend/data/` directory to retain everything you need for a full
restore.

## 9. Roadmap + TODOs
- **TODO:** Publish an official Docker image to GitHub Container Registry and
  reference it in this guide.
- **TODO:** Update the onboarding section once the frontend ships the admin
  walkthrough.
- Consider setting `ADE_AUTH_TOKEN_SECRET` to a long random value before going
  beyond local testing.

With these basics you can run ADE on a laptop, VM, or container host and manage
administrators confidently using the CLI.

## 10. Troubleshooting
- **`ade start` exits immediately:** ensure you ran `npm install` inside `frontend/` and that `uvicorn` is available (re-run `pip install -e .[dev]`).
- **Port conflicts (8000/5173):** pass `--backend-port` / `--frontend-port` to `ade start`, or stop whatever process currently occupies those ports.
- **Coloured logs appear garbled on Windows:** rerun with `ade start --no-color`.
- **Frontend cannot reach the API:** set `--vite-api-url http://127.0.0.1:8000` when the backend runs on a different host or port.






