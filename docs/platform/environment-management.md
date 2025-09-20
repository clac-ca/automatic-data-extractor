---
Audience: Platform administrators
Goal: Manage ADE configuration files, environment variables, and secrets across local, staging, and production environments.
Prerequisites: Ability to edit `.env` files, restart ADE services, and access the organisation's secret storage.
When to use: Apply this guide whenever you prepare a new ADE environment, rotate credentials, or audit stored secrets.
Validation: Restart ADE, confirm `GET /health` returns `{ "status": "ok" }`, and verify updated paths or credentials take effect.
Escalate to: Platform owner or security lead if secrets leak, drift cannot be corrected, or required credentials are missing.
---

# Environment and secret management

ADE reads configuration from a mix of defaults, `.env` files, and process-level environment variables. The backend caches settings at startup, so every change should be deliberate and followed by a validation check.

## Configuration layers at a glance

Start with the simple priority order below. Each layer overrides the one beneath it.

| Layer | Example | Purpose | Override behaviour |
| --- | --- | --- | --- |
| Code defaults | `Settings.data_dir = Path("data")` | Reasonable local defaults tracked in Git | Lowest priority |
| `.env` file | `.env`, `.env.local`, `.env.staging` | Store secrets for a specific environment | Overrides defaults |
| Process environment | `ADE_DATABASE_URL`, `ADE_SSO_CLIENT_SECRET` | Temporary overrides from shells, CI, or hosts | Highest priority |

Confirm which values ADE is using by printing the settings inside an activated virtual environment.

```powershell
python -c "from backend.app.config import get_settings, reset_settings_cache; reset_settings_cache(); settings = get_settings(); print(settings.model_dump())"
```

## Prepare environment-specific files

Keep the repository root clean by storing one template per environment. Copy the file you need into `.env` before launching ADE.

```powershell
# Example layout
type .env.example
# Copy a template into place for local runs
Copy-Item .env.local .env -Force
```

Populate each file with the secrets relevant to that environment. Use comments to remind future maintainers how to refresh values.

```dotenv
# .env.local
ADE_DATA_DIR=data
# ADE_DATABASE_URL=sqlite:///data/db/ade.sqlite
# Uncomment to require manual schema upgrades instead of auto-migrating
# ADE_AUTO_MIGRATE=false
ADE_AUTH_MODES=basic
ADE_SESSION_TTL_MINUTES=720
# Rotate when you refresh sample SSO metadata
ADE_SSO_CLIENT_SECRET=local-dev-client-secret
```

By default ADE detects file-based SQLite URLs and applies Alembic migrations on startup. Leave `ADE_AUTO_MIGRATE` unset to rely on the automatic behaviour, or export `ADE_AUTO_MIGRATE=false` before booting if you need to run `python -m backend.app.db_migrations upgrade` (or `alembic upgrade head`) manually.

When you switch environments (for example, from staging to production), overwrite `.env` with the appropriate template and delete any leftover files from your working directory.

## Rotate secrets on a schedule

Sensitive values should follow a predictable cadence. Treat the table below as the baseline and adjust to satisfy organisational policies.

| Secret | Source | Suggested rotation |
| --- | --- | --- |
| `ADE_SSO_CLIENT_SECRET` | Identity provider | Quarterly or immediately after incidents |
| `ADE_SESSION_COOKIE_SECRET` (future hardening) | Secrets manager | Rotate with every release |
| `ADE_DATABASE_URL` credentials (if using Postgres) | Database owner | Regenerate when operators change or quarterly |

Store the authoritative copy of each secret in the organisation's vault. Update `.env` files only with short-lived values you can safely rotate.

## Restart after every change

`backend/app/config.py` caches the loaded settings through `get_settings()`. Restart the backend whenever you update `.env` or export a new `ADE_` variable.

```powershell
# Stop the running server (Ctrl+C) and restart it
python -m uvicorn backend.app.main:app --reload

# Validate the service came back and is using the desired database
Invoke-WebRequest http://127.0.0.1:8000/health | Select-Object -ExpandProperty Content
Get-Item data\db\ade.sqlite
```

For hosted environments, redeploy the service or trigger the process supervisor (systemd, Azure Container Apps, etc.) to restart the container so fresh settings load.

## Protect the `data/` directory

The `data/` directory holds uploaded documents and the SQLite database. Treat it as sensitive data:

- Keep it out of version control (`data/` already appears in `.gitignore`).
- Restrict permissions so only the ADE service account can read the contents.
- Back up the entire directory when you snapshot the environment (database and documents should move together).

When the directory moves to shared storage or cloud buckets, ensure the same protections apply.

## Where to look next

- Review the [environment variables reference](../reference/environment-variables.md) for a complete list of supported settings.
- Pair this guide with the [local quickstart](./quickstart-local.md) when you bootstrap a fresh laptop.
- Document hosted-deployment overrides (for example, Azure Container Apps) in dedicated runbooks once those environments go live.
