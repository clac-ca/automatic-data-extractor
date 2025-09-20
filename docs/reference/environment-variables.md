---
Audience: Platform administrators, Data teams
Goal: Capture ADE configuration settings and defaults as defined in `backend/app/config.py`.
Prerequisites: Ability to edit deployment environment variables and restart ADE services.
When to use: Review when configuring new environments, auditing security posture, or troubleshooting behaviour tied to settings.
Validation: After changing settings, compare against `backend/app/config.py` and call `GET /health` (and other relevant endpoints) to confirm the new values applied.
Escalate to: Platform owner when runtime behaviour does not match the documented defaults or allowed values.
---

# Environment variables

ADE reads all runtime configuration through `backend/app/config.py`. The table below groups settings by theme, documenting defaults, allowed values, and whether a service restart is required (most changes need one because settings are cached at startup).

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

## Authentication and sessions

| Variable | Default | Allowed values / notes | Restart required |
| --- | --- | --- | --- |
| `ADE_AUTH_MODES` | `basic` | Comma-separated list drawn from `none`, `basic`, `sso`. `none` cannot combine with others. | Yes |
| `ADE_SESSION_COOKIE_NAME` | `ade_session` | Non-empty string; browser cookie name. | Yes |
| `ADE_SESSION_TTL_MINUTES` | `720` | Positive integer; minutes before sessions expire. | No (affects next refresh) |
| `ADE_SESSION_COOKIE_SECURE` | `false` | `true` / `false`; mark cookies as Secure. Required when SameSite=`none`. | Yes |
| `ADE_SESSION_COOKIE_DOMAIN` | _(unset)_ | Optional domain attribute for the session cookie. | Yes |
| `ADE_SESSION_COOKIE_PATH` | `/` | Cookie path. | Yes |
| `ADE_SESSION_COOKIE_SAME_SITE` | `lax` | `lax`, `strict`, or `none`. Validation enforced in `Settings._validate_same_site`. | Yes |

Validation tip: After adjusting session settings, log in via `/auth/login` and inspect returned cookies to verify attributes.

## SSO configuration

| Variable | Default | Allowed values / notes | Restart required |
| --- | --- | --- | --- |
| `ADE_SSO_CLIENT_ID` | _(unset)_ | Required when enabling `sso` mode. | Yes |
| `ADE_SSO_CLIENT_SECRET` | _(unset)_ | Required when enabling `sso` mode; used for state token signing. | Yes |
| `ADE_SSO_ISSUER` | _(unset)_ | Base URL for the OIDC provider discovery document. | Yes |
| `ADE_SSO_REDIRECT_URL` | _(unset)_ | Must match registered redirect URL. | Yes |
| `ADE_SSO_AUDIENCE` | _(unset)_ | Optional expected audience; defaults to client ID. | Yes |
| `ADE_SSO_SCOPES` | `openid email profile` | Space-delimited list of requested scopes. | Yes |
| `ADE_SSO_CACHE_TTL_SECONDS` | `300` | Positive integer; cache lifetime for discovery and JWKS payloads. | No (clears automatically after TTL or on restart) |
| `ADE_SSO_AUTO_PROVISION` | `false` | `true` / `false`; automatically create users for valid SSO identities. | Yes |

Validation tip: Hit `/auth/sso/login` after configuration. Inspect redirect URLs and ensure JWKS responses refresh within the configured cache window. Use `python -m backend.app.auth.sso clear_caches` (via Python REPL) or restart ADE to clear caches early.

## Integration credentials (roadmap)

| Variable | Default | Allowed values / notes | Restart required |
| --- | --- | --- | --- |
| `ADE_API_KEY` | _(unset)_ | Reserved for the upcoming API key feature. Store per-integration secrets here so clients can forward them as the `ADE-API-Key` header when support lands. | No (header-based) |

Until keys are live, leave the variable unset. Clients relying on it should fall back to session cookies without additional configuration changes.

## Administrative controls

| Variable | Default | Allowed values / notes | Restart required |
| --- | --- | --- | --- |
| `ADE_ADMIN_EMAIL_ALLOWLIST_ENABLED` | `false` | `true` / `false`; enforce administrator allowlist. | Yes |
| `ADE_ADMIN_EMAIL_ALLOWLIST` | _(unset)_ | Comma-separated list of email addresses permitted to hold admin role. | Yes |

When toggling allowlist enforcement, verify administrator logins and run `python -m backend.app.auth.manage list-users` to confirm only expected accounts retain elevated roles.

## Cache resets during runtime

ADE caches settings via `backend/app/config.get_settings()`. To re-read environment variables without a full restart in development, call `config.reset_settings_cache()` inside a Python shell before reloading components. Production deployments should restart the process to guarantee consistency.
