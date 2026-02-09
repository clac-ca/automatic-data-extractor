# Environment Variables

This page explains the main `ADE_*` settings in plain language.

## Start Here (Minimum Required for Production)

Set these first for Azure Container Apps production:

| Variable | Why you need it |
| --- | --- |
| `ADE_PUBLIC_WEB_URL` | Public HTTPS URL users will open |
| `ADE_DATABASE_URL` | Database connection string |
| `ADE_SECRET_KEY` | Security key for sessions/tokens |
| `ADE_BLOB_CONTAINER` | Blob container name for files |
| `ADE_BLOB_ACCOUNT_URL` **or** `ADE_BLOB_CONNECTION_STRING` | Blob authentication (set exactly one, prefer `ADE_BLOB_ACCOUNT_URL` + managed identity) |

If one of these is missing, production startup will fail.

## How to Read This Page

- **Required Scope** means where the variable is required.
- **Default** means what ADE uses if you do not set it.
- Some values are **compose defaults**, not code defaults.
- Azure Container Apps does not read compose defaults; set production values explicitly.

## Core Runtime

| Variable | Component | Required Scope | Default | Notes |
| --- | --- | --- | --- | --- |
| `ADE_DATABASE_URL` | API, worker, DB CLI | all environments | none | PostgreSQL connection string |
| `ADE_SECRET_KEY` | API | all environments | none | 32+ bytes required; 64+ recommended |
| `ADE_BLOB_CONTAINER` | API, worker, storage | all environments | `ade` | blob container name |
| `ADE_BLOB_CONNECTION_STRING` | API, worker, storage | one-of required | none | key-based blob auth |
| `ADE_BLOB_ACCOUNT_URL` | API, worker, storage | one-of required | none | identity-based blob auth |
| `ADE_PUBLIC_WEB_URL` | API/web behavior | production | `http://localhost:8000` | must match real external URL |

## Service Selection and Startup

| Variable | Component | Required Scope | Default | Notes |
| --- | --- | --- | --- | --- |
| `ADE_SERVICES` | root CLI/container | optional | `api,worker,web` | choose which services to run |
| `ADE_DB_MIGRATE_ON_START` | root CLI | optional | `true` | auto-runs migrations with `ade start/dev` |
| `ADE_API_PORT` | API CLI (`ade-api`) | optional | `8001` | API bind port for native CLI runs |
| `ADE_WEB_PORT` | web CLI (`ade web dev`) | optional | `8000` | Vite web dev server port for native CLI runs |
| `ADE_INTERNAL_API_URL` | web/nginx/vite | optional | `http://localhost:8001` | must be origin only (no path/query) |
| `ADE_DATA_DIR` | API, worker | optional | `backend/data` (repo) or `/app/data` (container) | writable runtime data path; mount this path for persistence in ACA |

For Azure Container Apps with persistent data, mount Azure Files to `/app/data`.
See [Production Bootstrap](../tutorials/production-bootstrap.md) for the exact mount workflow.

## Auth and Security

| Variable | Component | Required Scope | Default | Notes |
| --- | --- | --- | --- | --- |
| `ADE_SAFE_MODE` | API/system | optional | unset (no override) | env override for `safeMode.enabled` runtime setting |
| `ADE_SAFE_MODE_DETAIL` | API/system | optional | unset (no override) | env override for `safeMode.detail` runtime setting |
| `ADE_AUTH_DISABLED` | API auth | dev-only optional | local compose `true`, app default `false` | never enable in production |
| `ADE_AUTH_DISABLED_USER_EMAIL` | API auth bypass | optional | `developer@example.com` | used only in auth-disabled mode |
| `ADE_AUTH_DISABLED_USER_NAME` | API auth bypass | optional | `Development User` | used only in auth-disabled mode |
| `ADE_ALLOW_PUBLIC_REGISTRATION` | API auth policy | optional | `false` | allows open user signup |
| `ADE_AUTH_MODE` | API auth policy | optional | `password_only` | runtime auth mode (`password_only`, `idp_only`, `password_and_idp`) |
| `ADE_AUTH_PASSWORD_RESET_ENABLED` | API auth policy | optional | `true` | enable/disable public forgot/reset password endpoints and UI |
| `ADE_AUTH_PASSWORD_MFA_REQUIRED` | API auth policy | optional | `false` | require MFA enrollment for password-authenticated sessions before protected API access |
| `ADE_AUTH_PASSWORD_MIN_LENGTH` | API auth policy | optional | `12` | minimum password length for password-authenticated flows |
| `ADE_AUTH_PASSWORD_REQUIRE_UPPERCASE` | API auth policy | optional | `false` | require uppercase in passwords |
| `ADE_AUTH_PASSWORD_REQUIRE_LOWERCASE` | API auth policy | optional | `false` | require lowercase in passwords |
| `ADE_AUTH_PASSWORD_REQUIRE_NUMBER` | API auth policy | optional | `false` | require numeric characters in passwords |
| `ADE_AUTH_PASSWORD_REQUIRE_SYMBOL` | API auth policy | optional | `false` | require symbols in passwords |
| `ADE_AUTH_PASSWORD_LOCKOUT_MAX_ATTEMPTS` | API auth policy | optional | `5` | failed password attempts before lockout |
| `ADE_AUTH_PASSWORD_LOCKOUT_DURATION_SECONDS` | API auth policy | optional | `300` | lockout duration in seconds after threshold is reached |
| `ADE_AUTH_IDP_JIT_PROVISIONING_ENABLED` | API auth policy | optional | `true` | runtime override for IdP JIT provisioning policy |
| `ADE_AUTH_SSO_PROVIDERS_JSON` | API SSO | optional | none | provider settings payload |
| `ADE_SSO_ENCRYPTION_KEY` | API SSO | optional | none | encryption key for SSO secrets |
| `ADE_SESSION_COOKIE_DOMAIN` | API sessions | optional | none | override cookie domain |
| `ADE_SESSION_COOKIE_NAME` | API sessions | optional | `ade_session` | session cookie name |
| `ADE_SESSION_CSRF_COOKIE_NAME` | API sessions | optional | `ade_csrf` | csrf cookie name |
| `ADE_SESSION_COOKIE_PATH` | API sessions | optional | `/` | cookie path |
| `ADE_SESSION_ACCESS_TTL` | API sessions | optional | `14 days` | session lifetime |

User provisioning controls are API-level (not env vars):

- `POST /api/v1/users` `passwordProfile.mode` (`explicit` or `auto_generate`)
- `POST /api/v1/users` `passwordProfile.forceChangeOnNextSignIn`

Auth transport contract:

- Browser auth uses session cookies + CSRF.
- API keys are accepted via `X-API-Key`.
- `Authorization: Bearer` is not an API-key transport.

### Runtime Settings Override Behavior

The runtime-setting env vars below are overrides, not primary storage:

- `ADE_SAFE_MODE`
- `ADE_SAFE_MODE_DETAIL`
- `ADE_AUTH_MODE`
- `ADE_AUTH_PASSWORD_RESET_ENABLED`
- `ADE_AUTH_PASSWORD_MFA_REQUIRED`
- `ADE_AUTH_PASSWORD_MIN_LENGTH`
- `ADE_AUTH_PASSWORD_REQUIRE_UPPERCASE`
- `ADE_AUTH_PASSWORD_REQUIRE_LOWERCASE`
- `ADE_AUTH_PASSWORD_REQUIRE_NUMBER`
- `ADE_AUTH_PASSWORD_REQUIRE_SYMBOL`
- `ADE_AUTH_PASSWORD_LOCKOUT_MAX_ATTEMPTS`
- `ADE_AUTH_PASSWORD_LOCKOUT_DURATION_SECONDS`
- `ADE_AUTH_IDP_JIT_PROVISIONING_ENABLED`

Runtime settings are resolved as:

1. env override
2. DB value (`application_settings.data`)
3. code default

When an override is present, the field is locked in API/UI and managed by environment + restart workflow.
Use [Manage Runtime Settings](../how-to/manage-runtime-settings.md) for full update examples and failure handling.

Removed auth env vars that are no longer accepted:

- `ADE_AUTH_EXTERNAL_ENABLED`
- `ADE_AUTH_FORCE_SSO`
- `ADE_AUTH_SSO_AUTO_PROVISION`
- `ADE_AUTH_ENFORCE_LOCAL_MFA`

## API and Worker Capacity

| Variable | Component | Required Scope | Default | Notes |
| --- | --- | --- | --- | --- |
| `ADE_API_PROCESSES` | API | optional | app default `1`; local compose default `2` | number of API processes (`ade-api start` / production); `ade dev` stays single-process reload by default |
| `ADE_API_THREADPOOL_TOKENS` | API | optional | `40` | AnyIO/Starlette sync threadpool token budget |
| `ADE_API_PROXY_HEADERS_ENABLED` | API | optional | `true` | enable trusted `X-Forwarded-*` parsing in Uvicorn |
| `ADE_API_FORWARDED_ALLOW_IPS` | API | optional | `127.0.0.1` | comma-separated trusted proxy IPs/CIDRs (`*` only in fully trusted networks) |
| `ADE_WORKER_RUN_CONCURRENCY` | worker | optional | app default `2`; local compose default `8` | runs processed in parallel per worker service |
| `ADE_WORKER_LEASE_SECONDS` | worker | optional | `900` | run claim lease length |
| `ADE_WORKER_BACKOFF_BASE_SECONDS` | worker | optional | `5` | retry backoff base |
| `ADE_WORKER_BACKOFF_MAX_SECONDS` | worker | optional | `300` | retry backoff cap |
| `ADE_WORKER_ENV_BUILD_TIMEOUT_SECONDS` | worker | optional | `600` | environment build timeout |
| `ADE_WORKER_RUN_TIMEOUT_SECONDS` | worker | optional | none | run timeout override |
| `ADE_WORKER_CACHE_DIR` | worker | optional | `/tmp/ade-worker-cache` | local worker cache root (venvs, uv cache, run temp dirs) |

## Logging

| Variable | Component | Required Scope | Default | Notes |
| --- | --- | --- | --- | --- |
| `ADE_LOG_FORMAT` | API, worker | optional | `console` | `console` or `json` |
| `ADE_LOG_LEVEL` | API, worker | optional | `INFO` | base log level |
| `ADE_API_LOG_LEVEL` | API | optional | inherits base | API log override |
| `ADE_WORKER_LOG_LEVEL` | worker | optional | inherits base | worker log override |
| `ADE_REQUEST_LOG_LEVEL` | API | optional | inherits API level | request log override |
| `ADE_ACCESS_LOG_ENABLED` | API | optional | `true` | access logs on/off |
| `ADE_ACCESS_LOG_LEVEL` | API | optional | inherits API level | access log override |
| `ADE_DATABASE_LOG_LEVEL` | API | optional | none | SQL log override |

## Database and Storage Advanced

| Variable | Component | Required Scope | Default | Notes |
| --- | --- | --- | --- | --- |
| `ADE_DATABASE_AUTH_MODE` | API, worker, DB CLI | optional | `password` | `password` or `managed_identity` |
| `ADE_DATABASE_SSLROOTCERT` | API, worker, DB CLI | optional | none | CA cert path |
| `ADE_DATABASE_POOL_SIZE` | API, worker | optional | `5` | DB pool size |
| `ADE_DATABASE_MAX_OVERFLOW` | API, worker | optional | `10` | DB pool overflow |
| `ADE_DATABASE_POOL_TIMEOUT` | API, worker | optional | `30` | seconds |
| `ADE_DATABASE_POOL_RECYCLE` | API, worker | optional | `1800` | seconds |
| `ADE_DATABASE_CONNECT_TIMEOUT_SECONDS` | API, worker | optional | `10` | seconds |
| `ADE_DATABASE_STATEMENT_TIMEOUT_MS` | API, worker | optional | `30000` | milliseconds |
| `ADE_DATABASE_CONNECTION_BUDGET` | API | optional | none | warn-only startup budget for estimated API DB connections |
| `ADE_BLOB_PREFIX` | API, worker, storage | optional | `workspaces` | blob path prefix |
| `ADE_BLOB_VERSIONING_MODE` | API, worker, storage | optional | `auto` | `auto`, `require`, `off` |
| `ADE_BLOB_REQUEST_TIMEOUT_SECONDS` | API, worker, storage | optional | `30` | request timeout |
| `ADE_BLOB_MAX_CONCURRENCY` | API, worker, storage | optional | `4` | transfer concurrency |
| `ADE_BLOB_UPLOAD_CHUNK_SIZE_BYTES` | API, worker, storage | optional | `4194304` | upload chunk size |
| `ADE_BLOB_DOWNLOAD_CHUNK_SIZE_BYTES` | API, worker, storage | optional | `1048576` | download chunk size |

## Retention and Limits

| Variable | Component | Required Scope | Default | Notes |
| --- | --- | --- | --- | --- |
| `ADE_STORAGE_UPLOAD_MAX_BYTES` | API | optional | `26214400` | max upload size |
| `ADE_CONFIG_IMPORT_MAX_BYTES` | API | optional | `52428800` | max config zip import bytes (applies to archive size and per-file extraction size) |
| `ADE_STORAGE_DOCUMENT_RETENTION_PERIOD` | API | optional | `30 days` | document retention |
| `ADE_DOCUMENTS_UPLOAD_CONCURRENCY_LIMIT` | API | optional | `8` | upload concurrency cap |
| `ADE_DOCUMENT_CHANGES_RETENTION_DAYS` | API | optional | `14` | change retention |
| `ADE_WORKER_CACHE_TTL_DAYS` | worker GC | optional | `30` | local worker cache retention (venv directories) |
| `ADE_WORKER_RUN_ARTIFACT_TTL_DAYS` | worker GC | optional | `30` | run artifact retention |

## Compose-Only Variables

These are for local/self-hosted compose usage, not Azure Container Apps runtime logic:

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `AZURITE_ACCOUNTS`
- `ADE_DOCKER_TAG` (image tag selection in compose)

## Network Controls (Azure-Level, Not ADE Variables)

These production controls are configured in Azure resources, not with `ADE_*` variables:

- PostgreSQL firewall rules (approved app/operator IPs)
- Storage firewall default deny plus IP rules
- Storage VNet rules with service endpoints for ACA subnet access

If you use public endpoints with allowlists, review these rules whenever app outbound IPs or operator network locations change.

## Managed Identity Patterns (Azure)

Recommended production pattern:

- Blob auth: set `ADE_BLOB_ACCOUNT_URL`, do not set `ADE_BLOB_CONNECTION_STRING`.
- Assign app managed identity `Storage Blob Data Contributor` on the blob container scope.
- Keep `ADE_DATABASE_AUTH_MODE=password` unless you have completed PostgreSQL Entra role setup.

PostgreSQL managed identity mode (optional advanced):

- set `ADE_DATABASE_AUTH_MODE=managed_identity`
- use a passwordless URL format for `ADE_DATABASE_URL`, for example:

```text
postgresql+psycopg://<db-role-name>@<server>.postgres.database.azure.com:5432/<db>?sslmode=require
```

- ensure the DB role exists and is mapped to the managed identity principal.

## Related References

- [CLI Reference](cli-reference.md)
- [Defaults Matrix](defaults-matrix.md)
- [Deploy to Production](../how-to/deploy-production.md)
- [Runtime Lifecycle](runtime-lifecycle.md)
