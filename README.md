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

ADE ships a single container defined in the root [`Dockerfile`](Dockerfile). A lightweight GitHub Actions workflow (`.github/workflows/docker-build.yml`) builds that image whenever changes land on `main` so we keep the production path healthy. Publishing to a registry will come later once the distribution story is finalised.

- The FastAPI application version is defined once in [`pyproject.toml`](pyproject.toml) and must follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
- The `main` branch build acts as a smoke test for the container, covering the frontend compilation and backend packaging steps in one run.

### Docker helpers

Use the root npm scripts as convenience wrappers around common Docker flows (they auto-build if the image is missing and surface a friendly error when Docker is unavailable):

- `npm run docker:build` – build `ade:local` from the root `Dockerfile`.
- `npm run docker:run` – launch the container on port 8000, wiring `.env` and persisting `./data` on Unix hosts (append `-- <docker flags>` to forward additional options).
- `npm run docker:test` – run a quick smoke check inside the image to ensure backend/frontend dependencies resolve.

### Cutting a release

1. Bump `project.version` in [`pyproject.toml`](pyproject.toml).
2. Add notes beneath the `## [Unreleased]` heading in [`CHANGELOG.md`](CHANGELOG.md).
3. Run `python scripts/finalize_changelog.py` to promote the unreleased section to the new `vX.Y.Z` entry. The script resets the "Unreleased" stub for the next iteration.
4. Commit the version, changelog, and related code changes using [Conventional Commits](CONTRIBUTING.md#commit-messages).
5. Open a pull request. Once it merges, the container workflow will rebuild the image as a smoke test for the production Dockerfile.

## Quickstart (local)

### Get set up

1. Install prerequisites (skip any you already have):
   - [Python 3.12](https://www.python.org/downloads/) with `pip`
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

3. Start the application server (add `--reload` while you're iterating locally):

   ```bash
   uvicorn backend.app.main:create_app --reload --factory --host 0.0.0.0 --port 8000
   ```

   This mirrors the production startup path: the FastAPI factory bootstraps the database directory (`data/db/`), applies Alembic migrations, and logs the resolved configuration before serving traffic. Override the bind address with `ADE_SERVER_HOST` / `ADE_SERVER_PORT` (for example `0.0.0.0:8000` inside a container) and provide a public origin with `ADE_SERVER_PUBLIC_URL` when reverse proxies sit in front of ADE. Time-based settings such as `ADE_JWT_ACCESS_TTL` accept either plain seconds (`900`) or suffixed strings like `15m`, `1h`, or `30d`. Prefer a convenience wrapper? `npm run start` shells out to uvicorn and automatically selects the virtualenv Python if it exists.

   The backend serves the compiled React application from `backend/app/web/static/`. Rebuild those assets by running `npm run build` from the repository root, which compiles the frontend and copies the output into place.

4. Inspect the active configuration:

   ```bash
   python - <<'PY'
   import json
   from backend.app.shared.core.config import get_settings

   settings = get_settings()
   print(json.dumps(settings.model_dump(mode="json"), indent=2))
   PY
   ```

   The snippet prints the resolved settings (post `.env` and environment overrides) with secrets masked. Pipe the JSON output into other tools when debugging deployments.

### Start each service manually (optional)

The uvicorn command above serves the prebuilt SPA from `backend/app/web/static/`. If you prefer Vite hot module reload while developing the frontend, run the backend and Vite dev server in separate terminals:

```bash
# Terminal 1 – backend (from repo root)
   uvicorn backend.app.main:create_app --reload --factory

# Terminal 2 – frontend
cd frontend
npm install  # first run only
npm run dev -- --host
```

The FastAPI application is created in [`backend/app/main.py`](backend/app/main.py). Configuration is loaded once at startup using the `Settings` model defined in [`backend/app/shared/core/config.py`](backend/app/shared/core/config.py) and cached on `app.state.settings`.

Open <http://localhost:8000/docs> to explore the autogenerated OpenAPI documentation. Docs are disabled by default; enable them with `ADE_API_DOCS_ENABLED=true`. The frontend sends requests to `/api` on the same origin during development.

### Type checking the backend

Run MyPy before submitting backend changes to ensure the `backend/app/` package stays on a clean baseline:

```bash
mypy backend/app
```

The configuration in `pyproject.toml` enables the Pydantic plugin and disallows implicit `Any` usage so missing type hints surface immediately.

## Architecture snapshot

ADE follows a feature-first layout inside the `backend/app/` package:

- [`backend/app/api`](backend/app/api) – minimal API shell (error handlers, settings dependency).
- [`backend/app/api/v1`](backend/app/api/v1) – top-level API router that composes feature routers.
- [`backend/app/features/auth`](backend/app/features/auth) – password, SSO, and API key flows plus access-control helpers.
- [`backend/app/features/documents`](backend/app/features/documents) – multipart uploads, metadata, downloads, and deletions.
- [`backend/app/features/jobs`](backend/app/features/jobs) – submission, status tracking, and synchronous execution via the pluggable processor contract.
- [`backend/app/features/workspaces`](backend/app/features/workspaces) – routing helpers and dependencies that enforce workspace-scoped URLs.
- [`backend/app/features/configs`](backend/app/features/configs) – configuration packages, version snapshots, and draft file management.
- [`backend/app/features/users`](backend/app/features/users) – identity management, roles, and repositories shared across features.
- [`backend/app/features/system_settings`](backend/app/features/system_settings) – repository and models for instance-wide configuration toggles.

Shared infrastructure lives under [`backend/app/shared`](backend/app/shared) – notably [`backend/app/shared/core`](backend/app/shared/core) for logging, middleware, settings, and other cross-cutting helpers plus [`backend/app/shared/db`](backend/app/shared/db) for SQLAlchemy metadata, mixins, and persistence utilities. React build artefacts are served from [`backend/app/web/static`](backend/app/web/static) by FastAPI.

Uploaded files and the SQLite database are stored beneath the [`data/`](data) directory by default. Override locations with the `ADE_STORAGE_DATA_DIR`, `ADE_DATABASE_DSN`, or `ADE_STORAGE_DOCUMENTS_DIR` environment variables when deploying to production systems.

> **Note**
> The container build currently runs as a smoke test on `main`. Update the admin guide with downstream deployment steps once registry publishing is enabled.

## Frontend readiness

ADE is ready for the upcoming web interface:

- [`backend/app/main.py`](backend/app/main.py) already serves the built single-page application from `/static`, falls back to `index.html` for unknown routes, and exposes the API under `/api`, so the React app can assume a unified origin.
- The root build script (`npm run build`) compiles the React Router application and syncs the bundle into `backend/app/web/static/`, keeping FastAPI and the SPA aligned for local and CI usage.
- Core routes now publish non-200 responses in the OpenAPI schema, giving the frontend typed failure contracts for authentication, documents, jobs, and workspace management.
- The [API Guide](docs/reference/api-guide.md) documents the shared error envelopes so the frontend can surface precise messages without re-inspecting backend code.
- Jobs execute through a typed processor contract (`JobProcessorRequest`/`JobProcessorResult`), so swapping in the real extractor or a mock from the frontend test suite only requires calling `set_job_processor` once.
- Settings follow standard FastAPI/Pydantic conventions with `ADE_` environment variables, so frontend and deployment tooling can rely on a predictable configuration surface.

### Frontend readiness checklist

The backend is ready for the forthcoming React SPA:

- **Consistent API surface.** Every router exposes documented success and error payloads, and jobs now return deterministic metrics/logs through the typed processor contract.
- **Session-based authentication.** Cookie + CSRF flows are enabled by default so browsers stay within standard security guidelines.
- **Static asset pipeline.** `npm run build` rebuilds the SPA and copies it into `backend/app/web/static/`, keeping local and production setups aligned.
- **Swap-in processors.** Use `set_job_processor` during end-to-end tests to fake extractor outputs without reaching for bespoke fixtures.

## Status

The backend is under active development. The high-level concepts above are stable; deeper guide content is being authored iteratively so it can track ongoing feature work without churn.
