---
Audience: Platform administrators, Data teams
Goal: Capture ADE configuration settings and defaults as defined in `backend/app/config.py`.
Prerequisites: Ability to edit deployment environment variables and restart ADE services.
When to use: Configure new environments, audit security posture, or troubleshoot behaviour tied to settings.
Validation: After changing settings, compare against `backend/app/config.py` and call `GET /health` (and other relevant
endpoints) to confirm the new values applied.
Escalate to: Platform owner when runtime behaviour does not match the documented defaults or allowed values.
---

# Environment variables

ADE reads all runtime configuration through `backend/app/config.py`. Settings are cached at startup; restart the API or call
`config.reset_settings_cache()` in development to pick up changes.

## Database and storage

| Variable | Default | Allowed values / notes | Restart required |
| --- | --- | --- | --- |
| `ADE_DATA_DIR` | `data` | Root directory for runtime artefacts (database, documents, caches). | Yes |
| `ADE_DATABASE_URL` | `sqlite:///data/db/ade.sqlite` | Any SQLAlchemy-compatible database URL. Derived from `ADE_DATA_DIR` when unset. | Yes |
| `ADE_DOCUMENTS_DIR` | `data/documents` | Absolute or relative path to the document storage directory. Defaults to `ADE_DATA_DIR/documents`. | Yes |
| `ADE_AUTO_MIGRATE` | _(auto)_ | When unset, ADE auto-applies Alembic migrations for file-based SQLite URLs. Set `false` to require manual upgrades or `true` to force auto-run for other backends. | Yes |
| `ADE_MAX_UPLOAD_BYTES` | `26214400` (25 MiB) | Positive integer representing upload size cap in bytes. | No (takes effect on next request) |

## Document retention and purge scheduler

| Variable | Default | Allowed values / notes | Restart required |
| --- | --- | --- | --- |
| `ADE_DEFAULT_DOCUMENT_RETENTION_DAYS` | `30` | Positive integer; governs fallback `expires_at` for uploads. | No (new uploads use updated value) |
| `ADE_PURGE_SCHEDULE_ENABLED` | `true` | `true` / `false`; controls background purge loop. | Yes (scheduler reads on startup) |
| `ADE_PURGE_SCHEDULE_RUN_ON_STARTUP` | `true` | `true` / `false`; whether to sweep immediately at boot. | Yes |
| `ADE_PURGE_SCHEDULE_INTERVAL_SECONDS` | `3600` | Integer ≥ 1; seconds between purge sweeps. | Yes |

Validation tip: After changing scheduler settings, restart ADE and check `GET /health` for the `purge` block to confirm the new cadence.

## Authentication

| Variable | Default | Allowed values / notes | Restart required |
| --- | --- | --- | --- |
| `ADE_AUTH_DISABLED` | `false` | `true` / `false`; bypasses authentication and issues an "anonymous" administrator identity for every request. | Yes |
| `ADE_JWT_SECRET_KEY` | _(unset)_ | Required when authentication is enabled. Provide a high-entropy symmetric secret. | Yes |
| `ADE_JWT_ALGORITHM` | `HS256` | Algorithm passed to PyJWT. `HS256` is recommended unless all clients support a different choice. | Yes |
| `ADE_ACCESS_TOKEN_EXP_MINUTES` | `60` | Positive integer; minutes until issued tokens expire. | Yes (tokens minted after the change honour the new value) |

Validation tip: After adjusting authentication settings, call `POST /auth/token` to ensure credentials are accepted and verify that unauthenticated requests receive `401 Not authenticated` responses.

## Runtime cache resets

`config.get_settings()` caches the loaded configuration. Call `config.reset_settings_cache()` inside a Python shell before reloading components in development. Production deployments should restart the process to guarantee consistency.
