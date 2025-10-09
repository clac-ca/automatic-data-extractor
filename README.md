# ADE — Automatic Data Extractor

Automatic Data Extractor (ADE) ingests semi-structured documents and turns them into tabular datasets. The project ships as a FastAPI backend with an in-process worker and optional React frontend. Operators interact with ADE exclusively through the HTTP API, which keeps automation, UI, and integrations aligned.

- **Deterministic jobs** – Extraction logic is revision-controlled so reruns produce identical outputs.
- **Workspace aware** – Every request is scoped to a workspace through URL paths like `/workspaces/{workspace_id}` for simple multi-tenancy.
- **Single API surface** – Upload documents, run jobs, and manage workspaces through the same FastAPI application.

## Documentation

Guides now live under the [`docs/`](docs/README.md) directory:

- [User Guide](docs/user-guide/README.md) – core workflows for documents, jobs, and workspace operations.
- [Admin Guide](docs/admin-guide/README.md) – deployment, configuration, and operational building blocks.
- [Reference glossary](docs/reference/glossary.md) – shared terminology across API payloads and database entities.

## Versioning, releases, and Docker images

ADE's published container images are built from `main` and hosted on GitHub Container Registry (GHCR) under `ghcr.io/<org>/automatic-data-extractor`.

- The FastAPI application version is defined once in [`pyproject.toml`](pyproject.toml) and must follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
- Pull requests trigger the Docker build to ensure the image continues to compile.
- Merges to `main` authenticate to GHCR, reuse the build cache, and push three tags:
  - `main` – the latest successful build from the default branch.
  - `sha-<short>` – the short commit SHA for traceability.
  - `vX.Y.Z` – emitted only when `project.version` is a valid semantic version.

### Cutting a release

1. Bump `project.version` in [`pyproject.toml`](pyproject.toml).
2. Add notes beneath the `## [Unreleased]` heading in [`CHANGELOG.md`](CHANGELOG.md).
3. Run `python scripts/finalize_changelog.py` to promote the unreleased section to the new `vX.Y.Z` entry. The script resets the "Unreleased" stub for the next iteration.
4. Commit the version, changelog, and related code changes using [Conventional Commits](CONTRIBUTING.md#commit-messages).
5. Open a pull request. Once it merges, the container workflow will publish the updated image to GHCR.

## Quickstart (local)

### Get set up

1. Install prerequisites (skip any you already have):
   - [Python 3.11](https://www.python.org/downloads/) with `pip`
   - [Node.js 20 LTS](https://nodejs.org/en/download/) (includes `npm`)
   - [Git](https://git-scm.com/downloads)

   ```bash
   python --version
   node --version
   npm --version
   git --version
   ```

2. Clone ADE and install dependencies:

   ```bash
   git clone https://github.com/your-org/automatic-data-extractor.git
   cd automatic-data-extractor
   cp .env.example .env

   python -m venv .venv
   # macOS / Linux
   source .venv/bin/activate
   # Windows PowerShell
   # .\.venv\Scripts\Activate.ps1

   python -m pip install --upgrade pip
   pip install -e .[dev]
   ```

3. Start the application server:

   ```bash
   ade start
   ```

   `ade start` performs a full bootstrap before launching `uvicorn` with reload enabled and serving the prebuilt SPA from `app/web/`:

   - creates the SQLite directory (`var/db/`) if it does not exist,
   - applies any pending Alembic migrations, and
   - emits a short summary of the effective settings so you can confirm the environment.

   If you need to rebuild frontend assets, add `--rebuild-frontend`. Additional quality-of-life flags include `--no-reload`, `--host`, `--port`, `--frontend-dir`, `--env KEY=VALUE`, and `--npm /path/to/npm`. Should the automatic bootstrap ever fail, fall back to the [manual migration checklist](docs/admin-guide/getting_started.md#manual-migrations-and-recovery) in the admin guide before restarting the service.

   Example: `ade start --rebuild-frontend --env ADE_LOGGING_LEVEL=DEBUG --env ADE_JWT_ACCESS_TTL=15m`
   Adjust the backend bind address with `ADE_SERVER_HOST` / `ADE_SERVER_PORT` (for example `0.0.0.0:8000` inside a container). Use `ADE_SERVER_PUBLIC_URL` for the public origin that browsers or webhooks should hit. Time-based settings such as `ADE_JWT_ACCESS_TTL` accept either plain seconds (`900`) or suffixed strings like `15m`, `1h`, or `30d`. The frontend targets the same origin at `/api`, so no additional configuration is required when you deploy both pieces together.

> Prefer installing from PyPI? Run `python -m pip install automatic-data-extractor`, but still clone the repository before you call `ade start` so the frontend sources are available.

4. Inspect the active configuration:

   ```bash
   ade settings
   ```

   The command prints the resolved settings (post `.env` and environment overrides) with secrets masked. Pipe the JSON output into other tools when debugging deployments.

### Start each service manually (optional)

`ade start` serves the prebuilt SPA from `app/web/`. If you prefer Vite hot module reload while developing the frontend, run the backend and Vite dev server in separate terminals:

```bash
# Terminal 1 – backend (from repo root)
uvicorn app.main:app --reload

# Terminal 2 – frontend
cd frontend
npm install  # first run only
npm run dev -- --host
```

The FastAPI application is created in [`app/main.py`](app/main.py). Configuration is loaded once at startup using the `Settings` model defined in [`app/core/config.py`](app/core/config.py) and cached on `app.state.settings`.

Open <http://localhost:8000/docs> to explore the autogenerated OpenAPI documentation. Docs are disabled by default; enable them with `ADE_API_DOCS_ENABLED=true`. The frontend sends requests to `/api` on the same origin during development.

### Admin CLI quickstart

Once dependencies are installed the `ade` command becomes available for user and API key administration:

```bash
# Bootstrap an administrator account
ade users create --email admin@example.com --password "S3cureP@ss" --role admin

# Issue an API key for scripting or service integrations
ade api-keys issue --email admin@example.com --json

# Reset credentials later using the email address
ade users set-password --email admin@example.com --password "N3wPass!"
```

The CLI prints human-readable tables by default, runs the same automatic database bootstrap before each command, and can emit JSON with `--json` for scripting. See the [admin getting started guide](docs/admin-guide/getting_started.md) for a deeper walkthrough of typical tasks, including the [manual migration fallback](docs/admin-guide/getting_started.md#manual-migrations-and-recovery) when automation cannot complete.

### Type checking the backend

Run MyPy before submitting backend changes to ensure the `app/` package stays on a clean baseline:

```bash
mypy app
```

The configuration in `pyproject.toml` enables the Pydantic plugin and disallows implicit `Any` usage so missing type hints surface immediately.

## Architecture snapshot

ADE follows a feature-first layout inside the `app/` package:

- [`app/api`](app/api) – the versioned router shell and shared dependency aliases consumed by FastAPI routes.
- [`app/features/auth`](app/features/auth) – password, SSO, and API key flows plus access-control helpers.
- [`app/features/documents`](app/features/documents) – multipart uploads, metadata, downloads, and deletions.
- [`app/features/jobs`](app/features/jobs) – submission, status tracking, and background execution via the in-process task queue.
- [`app/features/workspaces`](app/features/workspaces) – routing helpers and dependencies that enforce workspace-scoped URLs.
- [`app/features/configurations`](app/features/configurations) – feature flags and per-workspace configuration records.
- [`app/features/users`](app/features/users) – identity management, roles, and repositories shared across features.
- [`app/features/system_settings`](app/features/system_settings) – repository and models for instance-wide configuration toggles.

Shared infrastructure lives under [`app/core`](app/core) (logging, middleware, settings, and cross-cutting helpers) and [`app/db`](app/db) (SQLAlchemy metadata, mixins, and persistence utilities). Background worker entry points now reside in [`app/workers`](app/workers), and React build artefacts are served from [`app/web`](app/web) by FastAPI.

Uploaded files and the SQLite database are stored beneath the [`var/`](var) directory by default. Override locations with the `ADE_STORAGE_DATA_DIR`, `ADE_DATABASE_DSN`, or `ADE_STORAGE_DOCUMENTS_DIR` environment variables when deploying to production systems.

> **Note**
> Automated GHCR publishing now runs from the `main` branch. Update the admin guide with downstream deployment steps once the frontend onboarding flow ships.

## Frontend readiness

ADE is ready for the upcoming web interface:

- [`app/main.py`](app/main.py) already serves the built single-page application from `/static`, falls back to `index.html` for unknown routes, and exposes the API under `/api`, so the React app can assume a unified origin.
- The `ade start` command and [`build_frontend_assets`](app/main.py) helper rebuild the frontend on demand, keeping `app/web/` in sync with the Vite output for local or CI usage.
- Core routes now publish non-200 responses in the OpenAPI schema, giving the frontend typed failure contracts for authentication, documents, jobs, and workspace management.
- The [API Guide](docs/reference/api-guide.md) documents the shared error envelopes so the frontend can surface precise messages without re-inspecting backend code.
- Jobs execute through a typed processor contract (`JobProcessorRequest`/`JobProcessorResult`), so swapping in the real extractor or a mock from the frontend test suite only requires calling `set_job_processor` once.
- Settings follow standard FastAPI/Pydantic conventions with `ADE_` environment variables, so frontend and deployment tooling can rely on a predictable configuration surface.

### Frontend readiness checklist

The backend is ready for the forthcoming React SPA:

- **Consistent API surface.** Every router exposes documented success and error payloads, and jobs now return deterministic metrics/logs through the typed processor contract.
- **Session-based authentication.** Cookie + CSRF flows are enabled by default so browsers stay within standard security guidelines.
- **Static asset pipeline.** `ade start --rebuild-frontend` rebuilds the SPA and serves it from the same origin at `/api`, keeping local and production setups aligned.
- **Swap-in processors.** Use `set_job_processor` during end-to-end tests to fake extractor outputs without reaching for bespoke fixtures.

## Status

The backend is under active development. The high-level concepts above are stable; deeper guide content is being authored iteratively so it can track ongoing feature work without churn.

