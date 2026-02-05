# Environment variables

This list focuses on the most common settings for local and production use.

## Core

- `ADE_DATABASE_URL` (required)
  - Example: `postgresql+psycopg://user:pass@host:5432/ade?sslmode=verify-full`
- `ADE_SECRET_KEY` (required)
  - 32+ bytes recommended.
- `ADE_DATA_DIR` (optional)
  - Default: `backend/data` (relative to the working directory).
  - Container recommendation: set to `/var/lib/ade/data` for persistent state outside the code mount.
- `ADE_WORKER_RUNS_DIR` (optional)
  - Default: `/tmp/ade-runs`

## Logging

- `ADE_LOG_FORMAT` (optional)
  - `console` (default) or `json`.
- `ADE_LOG_LEVEL` (optional)
  - Global default level for service logs (`INFO` default).
  - Allowed values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
- `ADE_API_LOG_LEVEL` (optional)
  - API-specific override. If unset, API uses `ADE_LOG_LEVEL`.
- `ADE_WORKER_LOG_LEVEL` (optional)
  - Worker-specific override. If unset, worker uses `ADE_LOG_LEVEL`.
- `ADE_REQUEST_LOG_LEVEL` (optional, API)
  - Override for API request-completion logger (`ade_api.request`).
- `ADE_ACCESS_LOG_ENABLED` (optional, API)
  - Controls uvicorn access logs (`true` default).
- `ADE_ACCESS_LOG_LEVEL` (optional, API)
  - Override for uvicorn access log level.
- `ADE_DATABASE_LOG_LEVEL` (optional, API)
  - Override for SQLAlchemy engine/pool logger levels.

Precedence:
- API effective level: `ADE_API_LOG_LEVEL` -> `ADE_LOG_LEVEL` -> `INFO`
- Worker effective level: `ADE_WORKER_LOG_LEVEL` -> `ADE_LOG_LEVEL` -> `INFO`

## Local filesystem layout

- Workspaces root: `ADE_DATA_DIR/workspaces`
- Run artifacts (worker): `ADE_WORKER_RUNS_DIR/<workspace_id>/runs/<run_id>`

## Database

- `ADE_DATABASE_AUTH_MODE` (optional)
  - `password` (default) or `managed_identity`
- `ADE_DATABASE_SSLROOTCERT` (optional)
  - Path to CA certificate.

## Blob storage

Choose one authentication method:

- `ADE_BLOB_CONNECTION_STRING`
- `ADE_BLOB_ACCOUNT_URL`

Additional settings:

- `ADE_BLOB_CONTAINER` (default: `ade`)
- `ADE_BLOB_PREFIX` (default: `workspaces`)
- `ADE_BLOB_REQUIRE_VERSIONING` (default: `true`)

## Service composition

- `ADE_SERVICES`
  - Comma-separated list: `api,worker,web`


## Web

Ports are fixed: web `8000`, API `8001`.
- `ADE_INTERNAL_API_URL`
  - Internal API upstream used by nginx and Vite (default: `http://localhost:8001`).
  - Use the base origin only (no `/api` path).
  - For split containers, set to `http://api:8001`.
- `ADE_PUBLIC_WEB_URL`
  - Public web URL used for redirects/cookies (default: `http://localhost:8000`).
- `ADE_WEB_VERSION_FILE`
  - Path to `version.json` for the web UI (default: `/usr/share/nginx/html/version.json`).
