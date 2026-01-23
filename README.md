# ADE — Automatic Data Extractor

[![CI](https://github.com/clac-ca/automatic-data-extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/clac-ca/automatic-data-extractor/actions/workflows/ci.yml)
[![Release](https://github.com/clac-ca/automatic-data-extractor/actions/workflows/release.yml/badge.svg)](https://github.com/clac-ca/automatic-data-extractor/actions/workflows/release.yml)

ADE turns messy spreadsheets into consistent, auditable workbooks.

It:

- Detects tables and columns in your source files
- Applies your custom rules and validation logic
- Produces normalized Excel workbooks with a detailed audit trail

---

## 1. Repository layout

```text
automatic-data-extractor/
├─ Dockerfile          # Full app image (API + worker + built web assets)
├─ .env.example        # Example environment configuration
├─ apps/
│  ├─ ade-api/         # FastAPI backend (API only)
│  ├─ ade-web/         # React (Vite) frontend SPA
│  ├─ ade-cli/         # Python CLI (console entry: `ade`)
│  ├─ ade-worker/      # Background worker (runs + environments)
│  └─ ade-engine/      # Engine runtime used by the worker/CLI
├─ docs/               # Developer docs & runbooks
├─ examples/           # Sample input/output files
├─ scripts/            # Helper / legacy scripts
└─ ...
````

Everything ADE produces at runtime (documents, runs, venvs, caches, etc.) goes under `./data/...` by default (inside the container: `/app/data`).

---

## 2. Quick start with Docker (recommended)

### 2.1 Prerequisites

* [Git](https://git-scm.com/downloads)
* [Docker](https://docs.docker.com/get-docker/)

### 2.2 Build and run the Docker image

```bash
# 1. Clone the repo
git clone https://github.com/clac-ca/automatic-data-extractor.git
cd automatic-data-extractor

# 2. Create local env file (edit as needed)
cp .env.example .env

# 3. Build the image
docker build -t ade:local -f Dockerfile .

# 4. Run the container (API + worker + web)
mkdir -p data
docker run --rm -p 8000:8000 --env-file .env -v "$(pwd)/data:/app/data" ade:local
```

Then open:

* **[http://localhost:8000](http://localhost:8000)**

The container runs `ade start`, which applies migrations on startup and serves the built frontend.

To run detached and stop later:

```bash
docker run -d --name ade -p 8000:8000 --env-file .env -v "$(pwd)/data:/app/data" ade:local
docker rm -f ade
```

---

## 3. Rebuilding the Docker container in development

When you change backend or frontend code and want a fresh container image:

```bash
docker build -t ade:local -f Dockerfile .
docker rm -f ade 2>/dev/null || true
docker run -d --name ade -p 8000:8000 --env-file .env -v "$(pwd)/data:/app/data" ade:local
```

---

## 4. Using the published image (no local build)

If you don’t want to build from source, you can run a published image from GHCR (when available).

```bash
# From inside the repo (for .env and ./data)
cp .env.example .env
mkdir -p data

docker pull ghcr.io/clac-ca/automatic-data-extractor:latest
docker run --rm -p 8000:8000 --env-file .env -v "$(pwd)/data:/app/data" ghcr.io/clac-ca/automatic-data-extractor:latest
```

Then go to **[http://localhost:8000](http://localhost:8000)**.

---

## 5. Local development (without Docker)

### 5.1 Prerequisites

* Python 3.11+
* Node.js 20 (or latest LTS)
* `git`
* **Azure SQL / SQL Server only:** system ODBC driver. Install `unixodbc` + Microsoft ODBC Driver 18 for SQL Server. On Debian/Ubuntu add the Microsoft repo (`packages-microsoft-prod.deb`, `sudo dpkg -i`, `sudo apt-get update`) then `sudo ACCEPT_EULA=Y apt-get install -y unixodbc msodbcsql18`; on macOS: `brew install unixodbc` and install the Microsoft ODBC Driver 18 package.

### 5.2 macOS / Linux

```bash
# Clone the repo
git clone https://github.com/clac-ca/automatic-data-extractor.git
cd automatic-data-extractor

# Create a local .env
cp .env.example .env

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade packaging tools
pip install -U pip setuptools wheel

# Install backend components in editable mode
pip install -e apps/ade-cli       # ADE CLI (console: `ade`)
pip install -e apps/ade-engine
pip install -e apps/ade-api
pip install -e apps/ade-worker

# Install frontend dependencies
(cd apps/ade-web && npm install)

# Quick verification (shows CLI help)
ade --help

# Start API + web dev servers + worker (runs migrations first)
ade dev

# Optional: skip worker or run it separately
ade dev --no-worker
ade worker
```

Dev URLs:

* API: **[http://localhost:8000](http://localhost:8000)**
* Web (Vite dev server): **[http://localhost:5173](http://localhost:5173)**

If needed, set `VITE_API_BASE_URL=http://localhost:8000` in `apps/ade-web/.env.local`.

### 5.3 Windows (PowerShell)

```powershell
git clone https://github.com/clac-ca/automatic-data-extractor.git
cd automatic-data-extractor

copy .env.example .env

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -U pip setuptools wheel

pip install -e apps/ade-cli
pip install -e apps/ade-engine
pip install -e apps/ade-api
pip install -e apps/ade-worker

cd apps/ade-web
npm install
cd ../..

ade dev
ade dev --no-worker  # skip worker if you want to run it separately
ade worker
```

---

## 6. ADE CLI basics

Once installed (locally or inside the container), the `ade` CLI provides useful commands:

* `ade dev` — run API + web dev servers + worker (runs migrations first)
* `ade dev --api-only` / `ade dev --web-only` — run just one surface
* `ade build` — build the web app (outputs to apps/ade-web/dist)
* `ade start` — run the API server + worker + built frontend (runs migrations first; builds frontend if missing; use `--no-web` if serving frontend separately)
* `ade worker` — run the background worker only
* `ade ci` — run the full CI suite (lint, tests, build)
* `ade users ...` — manage users (list/create/update, assign or remove roles)

Tip: `ade dev` and `ade start` run migrations automatically; use `ade migrate` manually when needed.

See `ade --help` for more options.

---

## 7. Configuration

ADE is configured via environment variables; the recommended way is:

1. Copy `.env.example` → `.env`
2. Adjust values as needed

Key variables (defaults assume `WORKDIR=/app` inside the container):

| Variable                  | Default                  | Purpose                                    |
| ------------------------- | ------------------------ | ------------------------------------------ |
| `ADE_DATA_DIR`            | `./data`                 | Root for local ADE storage (workspaces, venvs, cache, db) |
| `ADE_SAFE_MODE`           | `false`                  | If `true`, skips engine execution          |
| `ADE_WORKER_CONCURRENCY`  | `1`                      | Worker concurrency per process             |
| `ADE_WORKER_POLL_INTERVAL`| `0.5`                    | Worker idle poll interval (seconds)        |
| `ADE_WORKER_ENV_BUILD_TIMEOUT_SECONDS` | `600`       | Wall‑clock timeout per environment build   |
| `ADE_WORKER_RUN_TIMEOUT_SECONDS` | `300`           | Wall‑clock timeout per run                 |
| `ADE_WORKER_ENABLE_GC`    | `1`                      | Enable worker GC (single-host default)     |
| `ADE_WORKER_ENV_TTL_DAYS` | `30`                     | Environment GC TTL (days)                  |
| `ADE_WORKER_RUN_ARTIFACT_TTL_DAYS` | `30`           | Run artifact GC TTL (days)                 |
| `ADE_WORKER_CPU_SECONDS`  | `60`                     | Best‑effort CPU limit per run              |
| `ADE_WORKER_MEM_MB`       | `512`                    | Best‑effort memory limit per run (MB)      |
| `ADE_WORKER_FSIZE_MB`     | `100`                    | Best‑effort max file size a run may create |

In Docker, these resolve under `/app`, so `./data/...` becomes `/app/data/...`.

---

## 8. CI & releases

* **CI (`.github/workflows/ci.yml`)**

  * Installs editable packages
  * Runs `ade ci` (OpenAPI checks, lint, tests, build)
  * Builds the Docker image from `./Dockerfile`
  * Pushes images to GHCR on `main` (tags: `latest`, `sha-<commit>`)

* **Releases (`.github/workflows/release.yml`)**

  * Reads the version from `apps/ade-api/pyproject.toml`
  * Uses `CHANGELOG.md` to create a GitHub Release
  * Builds and pushes versioned images:

    * `ghcr.io/clac-ca/automatic-data-extractor:<version>`
    * `ghcr.io/clac-ca/automatic-data-extractor:latest`

To pull a specific image:

```bash
docker pull ghcr.io/clac-ca/automatic-data-extractor:<tag>
```

---

## 9. Contributing

* Open issues or PRs on GitHub
* Before opening a PR:

  * Run `ade ci` locally if possible, or
  * Mirror the steps in `.github/workflows/ci.yml`

---

## 10. License

See [LICENSE](LICENSE).
