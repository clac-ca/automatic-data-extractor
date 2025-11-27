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
├─ Dockerfile          # Main app image: API + built SPA
├─ compose.yaml        # Local Docker stack (single service: ade)
├─ .env.example        # Example environment configuration
├─ apps/
│  ├─ ade-api/         # FastAPI backend (serves /api + static SPA)
│  ├─ ade-web/         # React (Vite) frontend SPA
│  ├─ ade-cli/         # Python CLI (console entry: `ade`)
│  └─ ade-engine/      # Engine runtime used by the API/CLI
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
* [Docker Compose](https://docs.docker.com/compose/install/) (often included in recent Docker Desktop installs)

### 2.2 Run ADE with Docker Compose

```bash
# 1. Clone the repo
git clone https://github.com/clac-ca/automatic-data-extractor.git
cd automatic-data-extractor

# 2. Create local env file (edit as needed)
cp .env.example .env

# 3. Build and start the app (API + SPA)
docker compose up --build
```

Then open:

* **[http://localhost:8000](http://localhost:8000)**

To stop the stack:

```bash
docker compose down
```

To start it again without rebuilding:

```bash
docker compose up -d
```

---

## 3. Rebuilding the Docker container in development

When you change backend or frontend code and want a fresh container image:

From the repo root:

```bash
# Rebuild the image and recreate the container
docker compose up --build
```

or, if the container is already running:

```bash
# Just rebuild the image
docker compose build

# Then restart the container
docker compose up -d
```

If you want to rebuild by hand:

```bash
# Build image directly
docker build -t ghcr.io/clac-ca/automatic-data-extractor:local .

# Run it
mkdir -p data
docker run -d \
  --name ade \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  --env-file .env \
  ghcr.io/clac-ca/automatic-data-extractor:local
```

---

## 4. Using the published image (no local build)

If you don’t want to build from source, you can run a published image from GHCR.

```bash
# From inside the repo (for .env and ./data)
cp .env.example .env
mkdir -p data

docker pull ghcr.io/clac-ca/automatic-data-extractor:latest

docker run -d \
  --name ade \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  --env-file .env \
  ghcr.io/clac-ca/automatic-data-extractor:latest
```

Then go to **[http://localhost:8000](http://localhost:8000)**.

To stop and remove the container:

```bash
docker stop ade
docker rm ade
```

---

## 5. Local development (without Docker)

### 5.1 Prerequisites

* Python 3.12 (or compatible 3.x)
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

# Install frontend dependencies
(cd apps/ade-web && npm install)

# Quick verification (shows CLI help)
ade --help

# Start backend + frontend dev servers (FastAPI + Vite)
ade dev
```

Dev URLs:

* API: **[http://localhost:8000](http://localhost:8000)**
* Web (Vite dev server): **[http://localhost:5173](http://localhost:5173)**

If needed, set `VITE_API_URL=http://localhost:8000` in `apps/ade-web/.env.local`.

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

cd apps/ade-web
npm install
cd ../..

ade dev
```

---

## 6. ADE CLI basics

Once installed (locally or inside the container), the `ade` CLI provides useful commands:

* `ade dev` — run backend + frontend dev servers
* `ade dev --backend-only` / `ade dev --frontend-only` — run just one surface
* `ade build` — build the frontend and bundle it into the backend static assets
* `ade start` — run the backend using the built SPA
* `ade ci` — run the full CI suite (lint, tests, build)

See `ade --help` for more options.

---

## 7. Configuration

ADE is configured via environment variables; the recommended way is:

1. Copy `.env.example` → `.env`
2. Adjust values as needed

Key variables (defaults assume `WORKDIR=/app` inside the container):

| Variable                  | Default                  | Purpose                                    |
| ------------------------- | ------------------------ | ------------------------------------------ |
| `ADE_WORKSPACES_DIR`      | `./data/workspaces`      | Root for all workspace storage             |
| `ADE_DOCUMENTS_DIR`       | `./data/workspaces`      | Base for documents (`<ws>/documents/...`)  |
| `ADE_CONFIGS_DIR`         | `./data/workspaces`      | Base for configs (`<ws>/config_packages/`) |
| *(venvs)*                 | _fixed_                  | Virtualenv lives at `<config_root>/.venv/` |
| `ADE_RUNS_DIR`            | `./data/workspaces`      | Base for runs (`<ws>/runs/<run_id>/...`)   |
| `ADE_PIP_CACHE_DIR`       | `./data/cache/pip`       | pip download/build cache                   |
| `ADE_SAFE_MODE`           | `false`                  | If `true`, skips engine execution          |
| `ADE_MAX_CONCURRENCY`     | `2`                      | Backend worker concurrency                 |
| `ADE_QUEUE_SIZE`          | `10`                     | Queue length before HTTP 429 backpressure  |
| `ADE_RUN_TIMEOUT_SECONDS` | `300`                    | Wall‑clock timeout per run                 |
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
