# ADE Admin Getting Started Guide

This handbook shows how to run and administer the Automatic Data Extractor (ADE)
without assuming prior context. ADE is designed to be a small, self-contained
service that relies on a bundled SQLite database, so you can evaluate it
anywhere without provisioning external infrastructure.

## 1. What ADE Ships With
- **Self-contained storage** – ADE persists all metadata in
  `data/db/ade.sqlite`. Documents and other artefacts live alongside it
  under `data/`. No external database service is required.
- **Deterministic FastAPI backend** – requests are handled by the app in
  `ade/main.py`. Background work stays inside the same process.
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
`data/db`, docs disabled outside `local`, etc.). Time-based settings
accept either plain seconds (`900`) or suffixed strings like `15m`, `1h`, or
`30d`, so you can stay consistent whether you configure them via `.env` or the
`ade start --env KEY=VALUE` flags.

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

2. Start the application server:

   ```bash
   ade start
   ```

   Each invocation performs an idempotent bootstrap before `uvicorn` comes online:

   - create the SQLite directory (`data/db/`) and its parents if they are missing,
   - run Alembic migrations in order, logging progress to the console, and
   - print a summary of the resolved settings (sourced from `.env` and the environment).

   Successful boot ends with the FastAPI reload server listening on the configured host and serving the compiled SPA from `ade/web/static/`, so <http://localhost:8000/> delivers both the UI and API. Use `--rebuild-frontend` to run the Vite production build and copy fresh assets before launch. Other helpful flags: `--no-reload`, `--host`, `--port`, `--frontend-dir`, `--env KEY=VALUE`, and `--npm /path/to/npm`.

3. Confirm the API is healthy:

   ```bash
   curl http://localhost:8000/health
   ```

All runtime state stays under `data/`. Stop the FastAPI process before deleting files and remove only the pieces you need to refresh. Deleting `data/db/` after the app stops resets the SQLite database; the next bootstrap recreates the directory and reapplies migrations automatically. Leave `data/documents/` intact unless you intend to delete uploaded sources.

### Run backend and frontend manually (optional)
`ade start` serves the prebuilt SPA. For frontend development with hot module reload, run the backend and the Vite dev server in separate terminals. Install dependencies in `frontend/` first (repeat only after dependency updates).

```bash
# Terminal 1
uvicorn ade.main:create_app --reload --factory

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
  -v "$(pwd)/data:/ade/data" \
  ade-backend:local \
  uvicorn ade.main:create_app --host 0.0.0.0 --port 8000 --factory
```

The bind mount keeps the SQLite database and documents on the host so they
survive container restarts. Check health the same way:

```bash
curl http://localhost:8000/health
```

When you deploy the frontend in production, compile it once (`ade start --rebuild-frontend` or `npm run build` followed by copying `frontend/dist/` into `ade/web/static/`). FastAPI serves those files directly, so your reverse proxy only
needs to forward requests to the backend.

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

Each invocation calls the same bootstrap helper as `ade start`, so SQLite
directories are created on demand and Alembic migrations run automatically
before any database session opens. Watch for the `Database bootstrap complete`
message before assuming changes have been applied.

From a virtual environment or any Python install where ADE is installed:

```bash
# Create the first administrator account
ade users create --email admin@example.com --password "TempPass123!" --role admin

# List existing users (JSON output is handy for scripts)
ade users list --json

# Reset a password without touching the database manually
ade users set-password --email admin@example.com --password-file ~/.secrets/new-password.txt

# Create a service account and issue a labelled API key
ade users create --email service@example.com --password "TempPass123!" --service-account --inactive --json
ade api-keys issue --email service@example.com --label "CI deployer" --expires-in 30 --json
ade api-keys revoke 01KZYXWVUTSRQPONML
```

Service accounts typically remain inactive so they cannot use password flows. Use descriptive labels when issuing keys to simplify audits.

When ADE runs in Docker, execute the same commands inside the container so they
share configuration:

```bash
docker exec -it ade-backend ade users create --email admin@example.com --password "TempPass123!" --role admin
```

> **Tip:** Because the CLI talks directly to the SQLite database, avoid running
> long CLI operations while ADE is actively processing heavy requests to keep
> contention low.

### Manual migrations and recovery

Automatic bootstrapping should cover both the API and CLI. If a deployment fails
before migrations run, use the same Alembic environment that powers the
bootstrap helper:

1. Stop the API or CLI process that encountered the failure.
2. Ensure the desired configuration is exported (source `.env` or forward the
   relevant environment variables).
3. From the repository root, run:

   ```bash
   alembic -c alembic.ini upgrade head
   ```

4. Restart the API or retry the CLI command.

If you need a clean slate, stop all ADE processes, remove `data/db/`, and start
the API or CLI again. The bootstrap helper recreates the directory, reapplies
migrations, and leaves other artefacts (such as `data/documents/`) untouched.
Capture a backup of `data/` before deleting anything if you may need to inspect
historical documents.

## 8. Where ADE Stores Data
- `data/db/ade.sqlite` – primary metadata database (SQLite).
- `data/documents/` – uploaded source files.
- `data/logs/` *(if enabled)* – structured JSON logs.

Back up the `data/` directory to retain everything you need for a full
restore.

## 9. Roadmap + TODOs
- **TODO:** Publish an official Docker image to GitHub Container Registry and
  reference it in this guide.
- **TODO:** Update the onboarding section once the frontend ships the admin
  walkthrough.
- Consider setting `ADE_JWT_SECRET` to a long random value before going
  beyond local testing.

With these basics you can run ADE on a laptop, VM, or container host and manage
administrators confidently using the CLI.

## 10. Troubleshooting
- **`ade start` exits immediately:** ensure the Python dependencies are installed (`pip install -e .[dev]`) and that the configured port is free. Run with `--no-reload` if you suspect the reload watcher cannot spawn a subprocess.
- **Port conflicts on 8000:** choose another port with `ade start --port 9000` or stop the conflicting process.
- **Frontend shows a blank page:** rebuild assets with `ade start --rebuild-frontend` (or run `npm run build` and copy `frontend/dist/` into `ade/web/static/`).
- **Frontend cannot reach the API:** ensure the backend is accessible at the same origin and that requests target the `/api` prefix.

