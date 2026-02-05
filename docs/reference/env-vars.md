# Environment variables

This page documents the primary `ADE_*` environment contract used by API, worker, and compose workflows.

## Compose behavior

- Compose reads `.env` for `${...}` interpolation.
- The repo compose files also pass `.env` into ADE containers at runtime.
- Create `.env` next to the compose file you run for ADE runtime settings.
- For compose-only controls (for example image tag selection), prefer shell/CI overrides per compose command.
- Local file: `docker-compose.yaml`
- Production files:
  - `docker-compose.prod.yaml` (single-container `app`)
  - `docker-compose.prod.split.yaml` (`app` + `worker`)

## Required (all environments)

- `ADE_DATABASE_URL`
  - Example: `postgresql+psycopg://user:pass@host:5432/ade?sslmode=verify-full`
- `ADE_SECRET_KEY`
  - Minimum 32 bytes (64+ recommended).
- `ADE_BLOB_CONTAINER`
  - Blob container name.
- Exactly one blob auth method (not both):
  - `ADE_BLOB_ACCOUNT_URL` (managed identity/AAD flow)
  - `ADE_BLOB_CONNECTION_STRING` (key-based / Azurite)

## Required for production compose files

- `ADE_PUBLIC_WEB_URL`
  - Public base URL (for redirects/cookies), for example `https://ade.example.com`.

## Production image selection

- `ADE_DOCKER_TAG`
  - Optional GHCR image tag for production compose files (compose-only, not ADE runtime).
  - Best set in shell/CI at deploy time instead of persisting in `.env`.
  - Takes effect when containers are recreated and image is pulled.
  - Default: `main` (image: `ghcr.io/clac-ca/automatic-data-extractor:<tag>`).

## Local dependency variables (compose-only)

- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
  - Used by local Postgres services in `docker-compose.yaml` and `.devcontainer/docker-compose.yaml`.
  - Not ADE runtime variables.
- `AZURITE_ACCOUNTS`
  - Used by local Azurite services in `docker-compose.yaml` and `.devcontainer/docker-compose.yaml`.
  - Not ADE runtime variable.
- If `POSTGRES_*` values are changed, ensure `ADE_DATABASE_URL` points to matching credentials/database.

## Service composition and startup

- `ADE_SERVICES`
  - Comma-separated: `api,worker,web`.
  - Usually set by compose for the container role.
- `ADE_DATA_DIR`
  - Runtime writable data root.
  - Container recommendation: `/var/lib/ade/data`.
- `ADE_DB_MIGRATE_ON_START`
  - `true|false`; auto-run migrations for `ade start` / `ade dev`.
- `ADE_DATABASE_MIGRATION_TIMEOUT_S`
  - Migration timeout in seconds; `<=0` disables timeout.

## Web/internal routing

- `ADE_INTERNAL_API_URL`
  - Internal upstream used by nginx/Vite.
  - Must be an origin only (no `/api` path, query, or fragment).
- `ADE_PUBLIC_WEB_URL`
  - Public URL for cookies and redirects.
- `ADE_WEB_VERSION_FILE`
  - Path to web `version.json` (default: `/usr/share/nginx/html/version.json`).

## Auth and security

- `ADE_SAFE_MODE`
  - Blocks engine execution paths when enabled.
- `ADE_AUTH_DISABLED`
  - Development-only auth bypass. Never enable in production.
- `ADE_AUTH_DISABLED_USER_EMAIL`
- `ADE_AUTH_DISABLED_USER_NAME`
- `ADE_ALLOW_PUBLIC_REGISTRATION`
- `ADE_AUTH_FORCE_SSO`
- `ADE_AUTH_SSO_AUTO_PROVISION`
- `ADE_AUTH_SSO_PROVIDERS_JSON`
- `ADE_SSO_ENCRYPTION_KEY`

## Logging

- `ADE_LOG_FORMAT`
  - `console` (default) or `json`.
- `ADE_LOG_LEVEL`
  - `DEBUG|INFO|WARNING|ERROR|CRITICAL`.
- `ADE_API_LOG_LEVEL`
- `ADE_WORKER_LOG_LEVEL`
- `ADE_REQUEST_LOG_LEVEL`
- `ADE_ACCESS_LOG_ENABLED`
- `ADE_ACCESS_LOG_LEVEL`
- `ADE_DATABASE_LOG_LEVEL`

## Database

- `ADE_DATABASE_AUTH_MODE`
  - `password` (default) or `managed_identity`.
- `ADE_DATABASE_SSLROOTCERT`
  - CA certificate path (optional).
- Pool and timeout tuning:
  - `ADE_DATABASE_ECHO`
  - `ADE_DATABASE_POOL_SIZE`
  - `ADE_DATABASE_MAX_OVERFLOW`
  - `ADE_DATABASE_POOL_TIMEOUT`
  - `ADE_DATABASE_POOL_RECYCLE`
  - `ADE_DATABASE_CONNECT_TIMEOUT_SECONDS`
  - `ADE_DATABASE_STATEMENT_TIMEOUT_MS`

## Storage and retention

- `ADE_BLOB_PREFIX` (default: `workspaces`)
- `ADE_BLOB_VERSIONING_MODE` (default: `auto`)
- `ADE_BLOB_REQUEST_TIMEOUT_SECONDS`
- `ADE_BLOB_MAX_CONCURRENCY`
- `ADE_BLOB_UPLOAD_CHUNK_SIZE_BYTES`
- `ADE_BLOB_DOWNLOAD_CHUNK_SIZE_BYTES`
- `ADE_STORAGE_UPLOAD_MAX_BYTES`
- `ADE_STORAGE_DOCUMENT_RETENTION_PERIOD`
- `ADE_DOCUMENTS_UPLOAD_CONCURRENCY_LIMIT`
- `ADE_DOCUMENT_CHANGES_RETENTION_DAYS`

### Blob versioning mode

- `ADE_BLOB_VERSIONING_MODE` controls ADE behavior only; it does not enable account-level versioning in Azure.
- `auto`: use version-aware operations when available; degrade gracefully when unsupported (for example Azurite).
- `require`: enforce version IDs on upload and fail fast if storage account versioning is unavailable.
- `off`: disable version-aware operations in ADE.
- Enable account-level blob versioning separately in Azure when running production with `auto` or `require`.
- Azure docs: https://learn.microsoft.com/en-us/azure/storage/blobs/versioning-overview
- Azurite support matrix: https://github.com/Azure/Azurite#support-matrix

## API

- `ADE_API_HOST`
- `ADE_API_WORKERS`
  - Uvicorn worker process count per container.
  - Default: `1` (when unset).
- `ADE_API_DOCS_ENABLED`
- `ADE_SERVER_CORS_ORIGINS`
- `ADE_SERVER_CORS_ORIGIN_REGEX`
- `ADE_ALGORITHM`
- `ADE_ACCESS_TOKEN_EXPIRE_MINUTES`
- `ADE_SESSION_COOKIE_DOMAIN`
- `ADE_SESSION_ACCESS_TTL`
- `ADE_SESSION_COOKIE_NAME`
- `ADE_SESSION_CSRF_COOKIE_NAME`
- `ADE_SESSION_COOKIE_PATH`

## Worker

- `ADE_WORKER_ID`
- `ADE_WORKER_CONCURRENCY`
  - Max concurrent run slots per worker container.
  - Default: `2`.
- `ADE_WORKER_LISTEN_TIMEOUT_SECONDS`
- `ADE_WORKER_CLEANUP_INTERVAL`
- `ADE_WORKER_LEASE_SECONDS`
- `ADE_WORKER_BACKOFF_BASE_SECONDS`
- `ADE_WORKER_BACKOFF_MAX_SECONDS`
- `ADE_WORKER_ENV_BUILD_TIMEOUT_SECONDS`
- `ADE_WORKER_RUN_TIMEOUT_SECONDS`
- `ADE_WORKER_ENV_TTL_DAYS`
- `ADE_WORKER_RUN_ARTIFACT_TTL_DAYS`
- `ADE_WORKER_RUNS_DIR`

## Engine package

- `ADE_ENGINE_SPEC`
  - Preferred engine requirement string.
- `ADE_ENGINE_PACKAGE_PATH`
  - Legacy worker alias for engine spec.
