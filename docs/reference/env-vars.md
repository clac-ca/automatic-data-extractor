# Environment variables

This list focuses on the most common settings for local and production use.

## Core

- `ADE_DATABASE_URL` (required)
  - Example: `postgresql+psycopg://user:pass@host:5432/ade?sslmode=verify-full`
- `ADE_SECRET_KEY` (required)
  - 32+ bytes recommended.
- `ADE_DATA_DIR` (optional)
  - Default: `data`
- `ADE_API_PORT` (optional)
  - Default: `8000` (API-only). When running with the web entrypoint on `8000`, set to `8001`.

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

- `ADE_WEB_PROXY_TARGET`
  - The API URL that nginx proxies to (web container).
- `ADE_WEB_DEV_PORT`
  - Port for the Vite dev server (default: `8000`).
- `ADE_API_PROXY_TARGET`
  - API base URL used by the Vite dev server proxy (default: `http://localhost:8001`).
- `ADE_WEB_VERSION_FILE`
  - Path to `version.json` for the web UI (default: `/usr/share/nginx/html/version.json`).
