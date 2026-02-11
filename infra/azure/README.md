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
| Container apps | images, replicas, app env overrides, secret key |
| Bootstrap admin | optional Entra login/object ID/type |

If bootstrap admin login/object ID are blank, scripts auto-resolve the current signed-in `az` user.

## Local Convenience Script

`infra/azure/deploy.sh` is a local, untracked convenience script.

Current setup note: in this repo it was recreated from `infra/azure/deploy.prod-dev.sh` values. You can regenerate it from `deploy.sh.example` or copy values from your local `deploy.prod-dev.sh` as needed.

## Validation

```bash
bash infra/azure/validate.sh
```
