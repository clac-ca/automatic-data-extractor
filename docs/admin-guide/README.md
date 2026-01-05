# Admin Guide

Administrators install, configure, and operate the Automatic Data Extractor. This guide captures the durable pieces of that workflow while deeper runbooks are drafted.

## Deployment at a glance
- ADE is a FastAPI application created in [`apps/ade-api/src/ade_api/main.py`](../../apps/ade-api/src/ade_api/main.py) with its settings defined in [`apps/ade-api/src/ade_api/settings.py`](../../apps/ade-api/src/ade_api/settings.py).
- Development uses `ade dev` to run the API, Vite dev server, and worker together (migrations run first). Use `--no-worker`, `--api-only`, or `--web-only` when you want fewer services. Use `ade start` for the prod-ish flow (builds frontend if missing, serves frontend + API + worker; runs migrations first). Add `--no-web` if you serve the frontend separately.
- Production deployments build the frontend once (`ade build`) and serve the static bundle behind the same reverse proxy that forwards API traffic to a managed ASGI process (Uvicorn, Uvicorn+Gunicorn, systemd, or a container orchestrator).
- Persistent state lives under the `data/` directory by default. SQLite databases sit under `data/db/`, and each workspace stores documents beneath `data/workspaces/<workspace_id>/documents/`. Override the roots with `ADE_DATABASE_URL`, `ADE_WORKSPACES_DIR`, or `ADE_DOCUMENTS_DIR` when relocating storage.
- The API and worker expect the schema to be migrated before startup. `ade dev` and `ade start` run migrations automatically; use `ade migrate` when you need a manual step (see the [admin getting started guide](getting_started.md#manual-migrations-and-recovery)).

## Configuration snapshot
- Settings are loaded once at startup through `get_settings()` and cached on `app.state.settings`. Routes read from this state rather than reloading environment variables on every request.
- Environment variables use the `ADE_` prefix (for example `ADE_DATABASE_URL`, `ADE_STORAGE_UPLOAD_MAX_BYTES`). A local `.env` file is respected during development.
- Set the externally reachable origin with `ADE_SERVER_PUBLIC_URL` and configure browser access via `ADE_SERVER_CORS_ORIGINS` (for example `["https://ade.example.com"]`). The uvicorn listener binds to the entrypoint defaults (0.0.0.0:8000 in Docker).
- Documentation endpoints (`/docs`, `/redoc`, `/openapi.json`) default on for the `local` and `staging` environments and can be
  toggled explicitly through the `ADE_API_DOCS_ENABLED` flag to keep production surfaces minimal.
- Account lockout policy is governed by `ADE_FAILED_LOGIN_LOCK_THRESHOLD` (attempts) and
  `ADE_FAILED_LOGIN_LOCK_DURATION` (lock length, supports suffixed durations like `5m`). Defaults lock a user for
  five minutes after five consecutive failures.

### Database configuration
- `ADE_DATABASE_URL` defaults to SQLite (`sqlite:///./data/db/ade.sqlite`). Point it at Azure SQL with an `mssql+pyodbc` URL when deploying.
- `ADE_DATABASE_AUTH_MODE` chooses authentication: `sql_password` (default) uses credentials embedded in the DSN; `managed_identity` strips username/password and injects an Entra token for Azure SQL.
- `ADE_DATABASE_MI_CLIENT_ID` optionally pins a user-assigned managed identity; omit it to use the system-assigned identity. Alembic migrations reuse the same settings and token flow as the runtime engine.

## Operational building blocks
- Database connections are created via the async SQLAlchemy engine in [`apps/ade-api/src/ade_api/db/database.py`](../../apps/ade-api/src/ade_api/db/database.py) with the request-scoped session dependency defined alongside it.
- Structured logging and correlation IDs are configured through [`apps/ade-api/src/ade_api/common/logging.py`](../../apps/ade-api/src/ade_api/common/logging.py) and middleware in [`apps/ade-api/src/ade_api/common/middleware.py`](../../apps/ade-api/src/ade_api/common/middleware.py).
- Run observability workflows (streaming, polling, DB inspection) are documented in [Observing ADE Runs](runs_observability.md) for on-call reference.

Future sections will expand on security hardening, backup procedures, and frontend onboarding once those pieces land. The components listed above are already in place and unlikely to change dramatically.

- [ADE Admin Getting Started Guide](getting_started.md) – local/python vs. Docker workflows, `.env` usage, and interim provisioning steps.
