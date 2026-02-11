# ADE Azure Infra

`infra/azure` contains ADE's Azure Bicep template and deploy scripts.

## What Is Bicep?

Azure Bicep is Microsoft's infrastructure-as-code language for ARM. You declare desired state; Azure applies it safely and incrementally.

Reference: https://learn.microsoft.com/azure/azure-resource-manager/bicep/overview

## Security Defaults

This flow is intentionally secure-by-default:

- PostgreSQL auth: Microsoft Entra only
- Blob auth: Microsoft Entra only (`ADE_BLOB_ACCOUNT_URL`)
- Access control: Entra group RBAC + database grants
- Group resolution: handled in deploy scripts (create/get)

## Safe To Re-Run?

Yes.

- ARM/Bicep deployment is incremental
- Role assignments use deterministic IDs
- Group create/get is idempotent
- PostgreSQL bootstrap/grants are idempotent

Important: this deployment owns the resources it configures. Re-running can overwrite manual portal changes (for example ingress/custom domain settings if they are not modeled in IaC or post-deploy scripts).

## Canonical Deploy Scripts

- Bash: `infra/azure/deploy.sh.example`
- PowerShell: `infra/azure/deploy.ps1.example`

Set `deploy_development_environment` in the script:

- `false`: production app only
- `true`: production + development apps (shared platform resources)

## Prerequisites

- Azure CLI (`az`)
- PostgreSQL client (`psql`)
- Permission to deploy to the target resource group
- Permission to create/read Entra groups
- Permission to create role assignments
- Permission to manage PostgreSQL Entra admin

## Quick Start (Bash)

```bash
cp infra/azure/deploy.sh.example infra/azure/deploy.sh
chmod +x infra/azure/deploy.sh
./infra/azure/deploy.sh
```

## Quick Start (PowerShell)

```powershell
Copy-Item infra/azure/deploy.ps1.example infra/azure/deploy.ps1
./infra/azure/deploy.ps1
```

## Input Groups (Top Of Script)

| Group | What you set |
| --- | --- |
| Azure context | `subscription_id`, `resource_group_name`, `location` |
| Naming | `workload`, `instance` |
| Deployment mode | `deploy_development_environment` |
| PostgreSQL | version/SKU/storage/firewall/allowlist/db names |
| Storage | `storage_account_sku_name` |
| Access control | `access_control_group_name_prefix` |
| Container apps | images, replicas, scale polling/cooldown/http concurrency, app env overrides, secret key |
| SSO bootstrap | enable flag, secret lifetime, auth mode, optional encryption key |
| Bootstrap admin | optional Entra login/object ID/type |

If bootstrap admin login/object ID are blank, scripts auto-resolve the current signed-in `az` user.

## Container App Health + Scale Defaults

Deploy scripts and Bicep defaults configure probes and autoscale behavior aligned with ADE routes:

- Startup probe: `GET /api/v1/health`
- Liveness probe: `GET /api/v1/health`
- Readiness probe: `GET /api/v1/health`
- HTTP scaling rule: concurrency target per replica (`*_scale_http_concurrent_requests`)
- Polling interval: `*_scale_polling_interval_seconds`
- Cooldown period: `*_scale_cooldown_period_seconds`

Development defaults are tuned for cost efficiency:

- `development_container_app_minimum_replicas=0`
- `development_container_app_scale_cooldown_period_seconds=1800` (30 minutes)

## SSO Auto-Provisioning

Deploy scripts can provision ADE SSO automatically with minimal setup:

- Separate Entra app registrations are used for production and development.
- ADE provider ID is `entra` in each environment.
- ADE provider label is always `Microsoft Entra ID`.
- Callback URI is set to `<ADE_PUBLIC_WEB_URL>/api/v1/auth/sso/callback`.
- `ADE_AUTH_SSO_PROVIDERS_JSON` is stored as a Container Apps secret reference.
- Scripts configure Entra optional claims automatically: `email`, `upn`, `verified_primary_email`, `xms_edov`.

### Identity Model (Standard)

ADE now uses Entra's immutable identity claims for sign-in identity:

- user key: `tid:oid` (tenant ID + object ID)
- email is profile data, not primary identity
- email resolution order: `email` -> `preferred_username` -> `upn`
- login does not depend on `email_verified` claims
- if an existing ADE account is matched by email, ADE requires a verification signal (`email_verified`, `verified_primary_email`, or `xms_edov`) before linking
- this is an intentional breaking auth-model change (no legacy fallback path)

Default script behavior:

- `enable_sso_bootstrap=true`
- `sso_client_secret_years=99`
- `sso_auth_mode=password_and_idp`
- `sso_idp_jit_provisioning_enabled=true`

### Entra App Naming Convention

The script defaults to CAF-style display names:

- `appreg-<workload>-prod-<region>-<instance>-sso-web`
- `appreg-<workload>-dev-<region>-<instance>-sso-web`

Examples:

- `appreg-ade-prod-canadacentral-001-sso-web`
- `appreg-ade-dev-canadacentral-001-sso-web`

### Required Entra Permissions

The deploy identity must be able to:

- create/update app registrations
- create app credentials (client secrets)
- update app optional claims
- read app registrations

Typical roles are `Application Administrator` or `Application Developer` (tenant policy dependent).

### 99-Year Secret Caveat

The script requests `--years 99` when creating client secrets. Some tenants block long-lived secrets by policy. If blocked, deployment fails fast with an explicit error so you can lower `sso_client_secret_years`.

## Local Convenience Script

`infra/azure/deploy.sh` is a local, untracked convenience script.

Current setup note: in this repo it was recreated from `infra/azure/deploy.prod-dev.sh` values. You can regenerate it from `deploy.sh.example` or copy values from your local `deploy.prod-dev.sh` as needed.

## Validation

```bash
bash infra/azure/validate.sh
```
