# Admin Guide

Administrators install, configure, and operate the Automatic Data Extractor. This guide captures the durable pieces of that workflow while deeper runbooks are drafted.

## Deployment at a glance
- ADE is a FastAPI application created in [`apps/ade-api/src/ade_api/main.py`](../../apps/ade-api/src/ade_api/main.py) with its settings defined in [`apps/ade-api/src/ade_api/settings.py`](../../apps/ade-api/src/ade_api/settings.py).
- Development uses `ade dev` to run the API, Vite dev server, and worker together (migrations run first). Use `--no-worker`, `--api-only`, `--web-only`, or `--worker-only` when you want fewer services. For production-style runs, build first (`ade build`) and then use `ade start` for the single-container flow (API + worker). Use `ade api start` / `ade worker start` for split containers. Add `--no-web` if you serve the frontend separately.
- Production deployments build the frontend once (`ade build`) and serve the static bundle behind the same reverse proxy that forwards API traffic to a managed ASGI process (Uvicorn, Uvicorn+Gunicorn, systemd, or a container orchestrator).
- Persistent state lives under the `data/` directory by default for local runtime artifacts (venvs, caches, config packages). Document blobs live in Azure Blob under `workspaces/<workspace_id>/files/<file_id>`. Override the local root with `ADE_DATA_DIR` when relocating on-disk storage.
- The API and worker expect the schema to be migrated before startup. `ade dev`, `ade start`, and `ade api start` run migrations automatically; use `ade api migrate` when you need a manual step (see the [admin getting started guide](getting_started.md#manual-migrations-and-recovery)).

## Configuration snapshot
- Settings are loaded once at startup through `get_settings()` and cached on `app.state.settings`. Routes read from this state rather than reloading environment variables on every request.
- Environment variables use the `ADE_` prefix (for example `ADE_DATABASE_URL`, `ADE_BLOB_ACCOUNT_URL`/`ADE_BLOB_CONNECTION_STRING`, `ADE_STORAGE_UPLOAD_MAX_BYTES`). A local `.env` file is respected during development.
- Set the externally reachable origin with `ADE_SERVER_PUBLIC_URL`. CORS is disabled by default; only set `ADE_SERVER_CORS_ORIGINS` or `ADE_SERVER_CORS_ORIGIN_REGEX` when the browser truly calls the API from a different origin (for example `["https://app.example.com"]`). The uvicorn listener binds to the entrypoint defaults (0.0.0.0:8000 in Docker).
- Documentation endpoints (`/docs`, `/redoc`, `/openapi.json`) default on for the `local` and `staging` environments and can be
  toggled explicitly through the `ADE_API_DOCS_ENABLED` flag to keep production surfaces minimal.
- Account lockout policy is governed by `ADE_FAILED_LOGIN_LOCK_THRESHOLD` (attempts) and
  `ADE_FAILED_LOGIN_LOCK_DURATION` (lock length, supports suffixed durations like `5m`). Defaults lock a user for
  five minutes after five consecutive failures.

### Database configuration
- `ADE_DATABASE_URL` is the canonical SQLAlchemy DSN used by the API, worker, and migrations (local dev defaults target the devcontainer Postgres service).
- `ADE_DATABASE_AUTH_MODE` chooses authentication: `password` (default) uses credentials embedded in the DSN; `managed_identity` injects an Entra token for Azure Database for PostgreSQL.
- `ADE_DATABASE_SSLROOTCERT` optionally supplies a CA path when using `verify-full`.

## Operational building blocks
- Database connections are created via the async SQLAlchemy engine in [`apps/ade-api/src/ade_api/db/database.py`](../../apps/ade-api/src/ade_api/db/database.py) with the request-scoped session dependency defined alongside it.
- Structured logging and correlation IDs are configured through [`apps/ade-api/src/ade_api/common/logging.py`](../../apps/ade-api/src/ade_api/common/logging.py) and middleware in [`apps/ade-api/src/ade_api/common/middleware.py`](../../apps/ade-api/src/ade_api/common/middleware.py).
- Run observability workflows (streaming, polling, DB inspection) are documented in [Observing ADE Runs](runs_observability.md) for on-call reference.

Future sections will expand on security hardening, backup procedures, and frontend onboarding once those pieces land. The components listed above are already in place and unlikely to change dramatically.

- [ADE Admin Getting Started Guide](getting_started.md) – local/python vs. Docker workflows, `.env` usage, and interim provisioning steps.
