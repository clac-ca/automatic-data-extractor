# ADE Azure Infra

`infra/azure` contains the Azure IaC and deployment scripts for ADE.

## What Is Bicep?

Azure Bicep is Microsoft's infrastructure-as-code language for Azure Resource Manager (ARM). You declare resources, and Azure converges the resource group to that state.

Reference: https://learn.microsoft.com/azure/azure-resource-manager/bicep/overview

## Security Model (Opinionated Defaults)

This deployment is intentionally secure-by-default and low-choice:

- PostgreSQL auth: Microsoft Entra only
- Blob auth: Microsoft Entra only (`ADE_BLOB_ACCOUNT_URL`, no shared key connection string)
- Access control: group-based RBAC + database grants are always applied
- Graph/Bicep extension is not used; groups are created/resolved in deployment scripts

## Safe To Re-Run?

Yes.

- ARM/Bicep deployment is incremental
- Role assignments use deterministic IDs (`guid(...)`)
- Group creation/lookup in scripts is idempotent
- PostgreSQL Entra bootstrap SQL uses idempotent role creation and safe repeated grants

## Deployment Entry Points

Use exactly one of these script flows:

1. Production only
- `infra/azure/deploy-prod.sh.example`
- `infra/azure/deploy-prod.ps1.example`

2. Production + development
- `infra/azure/deploy-prod-dev.sh.example`
- `infra/azure/deploy-prod-dev.ps1.example`

No other operator path is required.

## Prerequisites

- Azure CLI (`az`) installed and authenticated
- PostgreSQL client (`psql`) installed
- Permission to deploy into target resource group
- Permission to create/read Entra groups
- Permission to create RBAC role assignments
- Permission to manage PostgreSQL Flexible Server Entra admins

## Required Script Inputs

Replace placeholders in the selected script before running.

| Input | Description |
| --- | --- |
| `<SUBSCRIPTION_ID>` | Azure subscription ID for deployment. |
| `resource_group_name` | Target resource group (script default is `rg-ade-shared-canadacentral-001`). |
| `location` | Azure region. |
| `workload` / `instance` | Naming tokens used in resource names. |
| `postgresql_*` sizing values | PostgreSQL version/SKU/storage/database names. |
| `public_ipv4_allowlist` | IPv4 addresses allowed to PostgreSQL/Storage public network rules. |
| `production_container_app_image` | Production ADE image tag. |
| `development_container_app_image` | Dev image tag (prod+dev scripts only). |
| `production_container_app_secret_key` | `ADE_SECRET_KEY` value. |
| `<POSTGRESQL_BOOTSTRAP_ENTRA_ADMIN_LOGIN>` | Entra login used to bootstrap PostgreSQL principals/grants. |
| `<POSTGRESQL_BOOTSTRAP_ENTRA_ADMIN_OBJECT_ID>` | Entra object ID for bootstrap admin principal. |
| `postgresql_bootstrap_entra_admin_type` | `User`, `Group`, or `ServicePrincipal`. |
| `access_control_group_name_prefix` | Prefix used to create/resolve canonical groups (`<prefix>-rg-*`, `<prefix>-ca-*`, `<prefix>-db-*`, `<prefix>-st-*`). |

## Option A: Deploy Production Only

### Bash

```bash
cp infra/azure/deploy-prod.sh.example infra/azure/deploy-prod.sh
chmod +x infra/azure/deploy-prod.sh
./infra/azure/deploy-prod.sh
```

### PowerShell

```powershell
Copy-Item infra/azure/deploy-prod.ps1.example infra/azure/deploy-prod.ps1
./infra/azure/deploy-prod.ps1
```

## Option B: Deploy Production + Development

### Bash

```bash
cp infra/azure/deploy-prod-dev.sh.example infra/azure/deploy-prod-dev.sh
chmod +x infra/azure/deploy-prod-dev.sh
./infra/azure/deploy-prod-dev.sh
```

### PowerShell

```powershell
Copy-Item infra/azure/deploy-prod-dev.ps1.example infra/azure/deploy-prod-dev.ps1
./infra/azure/deploy-prod-dev.ps1
```

## What The Script Does

1. Creates/ensures canonical Entra groups exist and resolves object IDs.
2. Runs `az deployment group create` with explicit required group object IDs.
3. Waits for PostgreSQL server readiness.
4. Sets bootstrap Entra admin on PostgreSQL with retry.
5. Creates DB principals and grants for app identities and db-readwrite/db-readonly groups.
6. Sets final PostgreSQL Entra admin to `<prefix>-db-admins`.

## FAQ

### Why are PostgreSQL username/password inputs not required?

The template only supports Entra auth for PostgreSQL. Password auth is intentionally removed.

### Why is there no `ADE_BLOB_CONNECTION_STRING` path?

Blob access is Entra-only. Container Apps use managed identity + `ADE_BLOB_ACCOUNT_URL`.

### Can I still use custom domains for the app URLs?

Yes. Configure custom domain in Azure Container Apps, then update `production_container_app_public_web_url` / `development_container_app_public_web_url` in the script and rerun.

References:
- https://learn.microsoft.com/azure/container-apps/custom-domains-certificates
- https://learn.microsoft.com/azure/container-apps/ingress-overview

### How do I run local infra validation?

```bash
bash infra/azure/validate.sh
```
