# ADE Azure Infra (Bicep)

This repo deploys Azure infrastructure from a single template: `infra/azure/main.bicep`.

## What Is Azure Bicep?

Azure Bicep is Microsoft's infrastructure-as-code language for Azure.  
You declare cloud resources in a `.bicep` file, and Azure Resource Manager (ARM) creates or updates them.

See [Bicep overview][bicep-overview].

## Is It Safe To Re-Run?

Yes.

- `az deployment group create` is designed to be re-run.
- ARM incremental deployment updates existing resources to match your template/parameters instead of duplicating resources.
- Use `az deployment group what-if` before `create` to preview changes.

See [deployment modes][arm-deployment-modes] and [what-if][arm-what-if].

## Option A: Deploy in Azure (single production-ready container app)

Use this when you only need production.

This deploys:

- Shared network and logging resources
- 1 Azure Container Apps environment
- 1 production container app (`api,worker,web`)
- 1 PostgreSQL Flexible Server with production database
- 1 Storage account with production blob container and file share

Full runnable command (all parameters, secure defaults = `microsoft_entra` for PostgreSQL and Blob):

```bash
az login
az account set --subscription "REPLACE_WITH_SUBSCRIPTION_ID"

# Optional pre-step: ensure target resource group exists (safe to re-run)
az group create --name "rg-ade-shared-canadacentral-001" --location "canadacentral"

az deployment group create \
  --resource-group "rg-ade-shared-canadacentral-001" \
  --name "ade-production-single-app" \
  --template-file infra/azure/main.bicep \
  --parameters \
    location="canadacentral" \
    workload="ade" \
    instance="001" \
    vnetCidr="10.80.0.0/16" \
    acaSubnetCidr="10.80.0.0/23" \
    postgresAdminUser="adeadmin" \
    postgresAdminPassword="REPLACE_WITH_STRONG_POSTGRES_PASSWORD" \
    postgresVersion="16" \
    postgresTier="Burstable" \
    postgresSkuName="Standard_B1ms" \
    postgresStorageSizeGb=32 \
    postgresProdDatabaseName="ade" \
    postgresDevDatabaseName="ade_dev" \
    postgresEntraAdminObjectId="REPLACE_WITH_ENTRA_OBJECT_ID_GUID" \
    postgresEntraAdminPrincipalName="REPLACE_WITH_ENTRA_UPN_OR_SERVICE_PRINCIPAL_NAME" \
    postgresEntraAdminPrincipalType="User" \
    postgresAllowAzureServicesRuleEnabled=true \
    postgresAuthenticationMethod="microsoft_entra" \
    storageSku="Standard_LRS" \
    storageBlobAuthenticationMethod="microsoft_entra" \
    allowedPublicIpAddresses='["REPLACE_WITH_PUBLIC_IPV4"]' \
    prodContainerAppImage="ghcr.io/clac-ca/automatic-data-extractor:REPLACE_WITH_PROD_TAG" \
    prodContainerAppPublicWebUrl="" \
    prodContainerAppEnvAdeSecretKey="REPLACE_WITH_ADE_SECRET_KEY_32_PLUS_BYTES" \
    prodContainerAppEnvOverrides='{"ADE_LOG_LEVEL":"INFO","ADE_LOG_FORMAT":"json"}' \
    prodContainerAppMinReplicas=1 \
    prodContainerAppMaxReplicas=2 \
    devContainerAppImage="" \
    devContainerAppPublicWebUrl="" \
    devContainerAppEnvAdeSecretKey="" \
    devContainerAppEnvOverrides='{}' \
    devContainerAppMinReplicas=0 \
    devContainerAppMaxReplicas=1
```

## Option B: Deploy in Azure (production + dev container apps using shared resources)

Use this when you want separate prod and dev apps (for example, dev runs a different image/tag).

This deploys:

- Shared network and logging resources
- 1 shared Azure Container Apps environment
- 2 container apps (1 x prod + 1 x dev)
- 1 PostgreSQL server with prod and dev databases
- 1 Storage account with prod and dev blob containers/file shares

Full runnable command (all parameters, secure defaults = `microsoft_entra` for PostgreSQL and Blob):

```bash
az login
az account set --subscription "REPLACE_WITH_SUBSCRIPTION_ID"

# Optional pre-step: ensure target resource group exists (safe to re-run)
az group create --name "rg-ade-shared-canadacentral-001" --location "canadacentral"

az deployment group create \
  --resource-group "rg-ade-shared-canadacentral-001" \
  --name "ade-production-and-dev-apps" \
  --template-file infra/azure/main.bicep \
  --parameters \
    location="canadacentral" \
    workload="ade" \
    instance="001" \
    vnetCidr="10.80.0.0/16" \
    acaSubnetCidr="10.80.0.0/23" \
    postgresAdminUser="adeadmin" \
    postgresAdminPassword="REPLACE_WITH_STRONG_POSTGRES_PASSWORD" \
    postgresVersion="16" \
    postgresTier="Burstable" \
    postgresSkuName="Standard_B1ms" \
    postgresStorageSizeGb=32 \
    postgresProdDatabaseName="ade" \
    postgresDevDatabaseName="ade_dev" \
    postgresEntraAdminObjectId="REPLACE_WITH_ENTRA_OBJECT_ID_GUID" \
    postgresEntraAdminPrincipalName="REPLACE_WITH_ENTRA_UPN_OR_SERVICE_PRINCIPAL_NAME" \
    postgresEntraAdminPrincipalType="User" \
    postgresAllowAzureServicesRuleEnabled=true \
    postgresAuthenticationMethod="microsoft_entra" \
    storageSku="Standard_LRS" \
    storageBlobAuthenticationMethod="microsoft_entra" \
    allowedPublicIpAddresses='["REPLACE_WITH_PUBLIC_IPV4"]' \
    prodContainerAppImage="ghcr.io/clac-ca/automatic-data-extractor:REPLACE_WITH_PROD_TAG" \
    prodContainerAppPublicWebUrl="" \
    prodContainerAppEnvAdeSecretKey="REPLACE_WITH_ADE_SECRET_KEY_32_PLUS_BYTES" \
    prodContainerAppEnvOverrides='{"ADE_LOG_LEVEL":"INFO","ADE_LOG_FORMAT":"json"}' \
    prodContainerAppMinReplicas=1 \
    prodContainerAppMaxReplicas=2 \
    devContainerAppImage="ghcr.io/clac-ca/automatic-data-extractor:REPLACE_WITH_DEV_TAG_OR_USE_PROD_IMAGE" \
    devContainerAppPublicWebUrl="" \
    devContainerAppEnvAdeSecretKey="REPLACE_WITH_DEV_ADE_SECRET_KEY_32_PLUS_BYTES_OR_EMPTY_TO_REUSE_PROD" \
    devContainerAppEnvOverrides='{"ADE_LOG_LEVEL":"DEBUG","ADE_LOG_FORMAT":"json"}' \
    devContainerAppMinReplicas=0 \
    devContainerAppMaxReplicas=1
```

URL defaults:

- `prodContainerAppPublicWebUrl=""` uses the generated production Container Apps URL.
- `devContainerAppPublicWebUrl=""` uses the generated dev Container Apps URL.
- Set either value to a custom HTTPS origin when you bind a custom domain.
- `deployDev` is optional. Dev resources auto-deploy when any dev parameter differs from defaults.
- Set `deployDev=true` only if you want dev deployed while keeping all dev parameters at default values.

Tip:

- Swap `create` with `what-if` to preview changes:
  - `az deployment group what-if ...`

Operational notes:

- PostgreSQL access: if `postgresAllowAzureServicesRuleEnabled=false` and `allowedPublicIpAddresses=[]`, no public client IPs are allowed and the app cannot connect to PostgreSQL over the public endpoint.
- PostgreSQL Microsoft Entra bootstrap: when `postgresAuthenticationMethod="microsoft_entra"`, this template creates DB roles/grants automatically via an idempotent deployment script.
- PostgreSQL bootstrap connectivity: the bootstrap script needs network access to PostgreSQL. If you disable `postgresAllowAzureServicesRuleEnabled`, ensure connectivity is still possible or use the manual fallback in the FAQ.
- Storage RBAC propagation: when `storageBlobAuthenticationMethod="microsoft_entra"`, blob role assignments can take up to 10 minutes to apply. Right after deployment, the app may restart until access is active. See [RBAC propagation][rbac-propagation].

Custom env vars:

- Add extra app env vars with `prodContainerAppEnvOverrides` and `devContainerAppEnvOverrides`.
- Example:
  - `prodContainerAppEnvOverrides='{"ADE_LOG_LEVEL":"INFO","ADE_LOG_FORMAT":"json"}'`
  - `devContainerAppEnvOverrides='{"ADE_LOG_LEVEL":"DEBUG"}'`
- Runtime throughput vars `ADE_API_PROCESSES` and `ADE_WORKER_RUN_CONCURRENCY` are intentionally left to application defaults in this template.
- Keys managed by this template/application defaults (for example `ADE_PUBLIC_WEB_URL`, `ADE_API_PROCESSES`, `ADE_WORKER_RUN_CONCURRENCY`, `ADE_DATABASE_URL`, `ADE_SECRET_KEY`, `ADE_DATABASE_AUTH_MODE`, `ADE_BLOB_ACCOUNT_URL`, `ADE_BLOB_CONNECTION_STRING`) are not overridden through these maps.
- Blob auth method is controlled by `storageBlobAuthenticationMethod`:
  - `microsoft_entra`: template sets `ADE_BLOB_ACCOUNT_URL` and creates RBAC role assignments.
  - `shared_key`: template sets `ADE_BLOB_CONNECTION_STRING` from the storage account key.

## Parameter Reference

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `location` | `string` | No | Resource group location | Azure region where resources are deployed. |
| `deployDev` | `bool` | No | `false` | Optional force switch for dev deployment. Normally omit it: dev resources are auto-deployed when any dev-specific parameter differs from default values. Set `true` to deploy dev with all-default dev parameters. |
| `workload` | `string` | No | `ade` | Naming token used in resource names. |
| `instance` | `string` | No | `001` | Naming token for instance/environment numbering. |
| `vnetCidr` | `string` | No | `10.80.0.0/16` | Shared VNet address space in [CIDR notation][cidr]. |
| `acaSubnetCidr` | `string` | No | `10.80.0.0/23` | Container Apps subnet address space in [CIDR notation][cidr]. |
| `postgresAdminUser` | `string` | No | `adeadmin` | PostgreSQL local admin username. Required by PostgreSQL Flexible Server and used when `postgresAuthenticationMethod="postgresql"`. |
| `postgresAdminPassword` | `secure string` | Yes | None | PostgreSQL local admin password. Required by PostgreSQL Flexible Server and used when `postgresAuthenticationMethod="postgresql"`. |
| `postgresVersion` | `string` | No | `16` | PostgreSQL major version. |
| `postgresTier` | `string` | No | `Burstable` | PostgreSQL compute tier. |
| `postgresSkuName` | `string` | No | `Standard_B1ms` | PostgreSQL SKU size (compute/memory class). |
| `postgresStorageSizeGb` | `int` | No | `32` | PostgreSQL storage size in GiB (minimum 32). |
| `postgresEntraAdminObjectId` | `string` | Yes | None | Entra object ID configured as PostgreSQL Entra admin. |
| `postgresEntraAdminPrincipalName` | `string` | Yes | None | Entra principal name configured as PostgreSQL Entra admin. |
| `postgresEntraAdminPrincipalType` | `string` | No | `User` | Entra principal type: `User`, `Group`, `ServicePrincipal`. |
| `postgresAllowAzureServicesRuleEnabled` | `bool` | No | `true` | Adds PostgreSQL `0.0.0.0` firewall rule ("Allow public access from any Azure service within Azure to this server"). See [PostgreSQL firewall rules][pg-firewall]. |
| `allowedPublicIpAddresses` | `array` | No | `[]` | Public IPv4 allowlist for PostgreSQL and Storage firewall/network rules. Empty means no explicit public IP allow rules. See [PostgreSQL firewall rules][pg-firewall] and [Storage IP rules][storage-ip-rules]. |
| `storageSku` | `string` | No | `Standard_LRS` | Storage redundancy/SKU. |
| `postgresAuthenticationMethod` | `string` | No | `microsoft_entra` | PostgreSQL authentication method used by the app. `postgresql` = password auth, `microsoft_entra` = token auth via managed identity. The template maps this to app env var `ADE_DATABASE_AUTH_MODE`. See [PostgreSQL auth modes][pg-auth]. |
| `storageBlobAuthenticationMethod` | `string` | No | `microsoft_entra` | Blob authentication method used by the app. `microsoft_entra` sets `ADE_BLOB_ACCOUNT_URL` + RBAC; `shared_key` sets `ADE_BLOB_CONNECTION_STRING` from storage account keys. See [Blob auth options][storage-auth]. |
| `postgresEntraBootstrapForceUpdateTag` | `string` | No | auto-generated GUID | Internal force-update token for the PostgreSQL Microsoft Entra bootstrap script. Leave as default in normal usage. |
| `postgresProdDatabaseName` | `string` | No | `ade` | PostgreSQL production database name. |
| `prodContainerAppImage` | `string` | Yes | None | Production Container App image. |
| `prodContainerAppPublicWebUrl` | `string` | No | `''` | Production Container App public HTTPS URL. Empty means use the generated default Container Apps URL. The template maps this to `ADE_PUBLIC_WEB_URL`. |
| `prodContainerAppEnvAdeSecretKey` | `secure string` | Yes | None | Container App env var `ADE_SECRET_KEY` for production (32+ bytes). |
| `prodContainerAppEnvOverrides` | `object` | No | `{}` | Additional production Container App env vars for production-specific behavior (for example `ADE_LOG_LEVEL`, `ADE_LOG_FORMAT`, `ADE_API_LOG_LEVEL`, `ADE_DATABASE_LOG_LEVEL`). |
| `prodContainerAppMinReplicas` | `int` | No | `1` | Minimum number of production [replicas][aca-replicas]. A replica is one running app instance. |
| `prodContainerAppMaxReplicas` | `int` | No | `2` | Maximum number of production [replicas][aca-replicas]. |
| `postgresDevDatabaseName` | `string` | No | `ade_dev` | PostgreSQL development database name (used when dev resources are deployed, either automatically from dev parameter usage or by `deployDev=true`). |
| `devContainerAppImage` | `string` | No | `''` | Development Container App image. Empty means use `prodContainerAppImage`. |
| `devContainerAppPublicWebUrl` | `string` | No | `''` | Development Container App public HTTPS URL. Empty means use the generated default Container Apps URL. The template maps this to `ADE_PUBLIC_WEB_URL`. |
| `devContainerAppEnvAdeSecretKey` | `secure string` | No | `''` | Container App env var `ADE_SECRET_KEY` for development. Empty means use production value. |
| `devContainerAppEnvOverrides` | `object` | No | `{}` | Additional development Container App env vars for dev-specific behavior (for example `ADE_LOG_LEVEL`, `ADE_LOG_FORMAT`, `ADE_API_LOG_LEVEL`, `ADE_DATABASE_LOG_LEVEL`). |
| `devContainerAppMinReplicas` | `int` | No | `0` | Minimum number of dev [replicas][aca-replicas]. |
| `devContainerAppMaxReplicas` | `int` | No | `1` | Maximum number of dev [replicas][aca-replicas]. |

## PostgreSQL Microsoft Entra Authentication (Recommended)

### Overview

Managed Identity allows the app to authenticate to Azure PostgreSQL **without storing database passwords**.
Azure issues short-lived access tokens to the app’s identity at runtime.
Blob authentication is configured independently via `storageBlobAuthenticationMethod`.

### Why Use It

* No database passwords in configuration or secrets
* Short-lived, token-based authentication
* Stronger security posture for production workloads

See: [Managed identities in Azure Container Apps][aca-mi]

---

### Enable Microsoft Entra Authentication

Start from **Option A** or **Option B** and set:

```bash
postgresAuthenticationMethod="microsoft_entra"
```

No extra SQL command is required.  
When `postgresAuthenticationMethod="microsoft_entra"`, the template runs an idempotent Azure deployment script that:

- Creates PostgreSQL roles for the Container App managed identities (prod and optional dev)
- Grants `CONNECT`, `CREATE`, and `TEMP` on each app database
- Safely re-runs on redeployments without duplicating principals

> **TIP — Switching an Existing Deployment**
> Bicep deployments are **safe and idempotent** to re-run.
> To switch an existing environment to Microsoft Entra auth, re-run the same deployment command with
> `postgresAuthenticationMethod="microsoft_entra"`.

## Teardown

```bash
az group delete --name "<RESOURCE_GROUP>" --yes --no-wait
```

## FAQ

**What does this Bicep template configure for authentication?**

- PostgreSQL: sets `ADE_DATABASE_AUTH_MODE` from `postgresAuthenticationMethod` (`microsoft_entra` or `postgresql`).
- Blob: sets either `ADE_BLOB_ACCOUNT_URL` (`microsoft_entra`) or `ADE_BLOB_CONNECTION_STRING` (`shared_key`).
- `ADE_SECRET_KEY` is set from `prodContainerAppEnvAdeSecretKey` / `devContainerAppEnvAdeSecretKey`.

**What does the PostgreSQL Microsoft Entra bootstrap script do?**

- Creates a dedicated user-assigned managed identity for bootstrap.
- Adds that identity as PostgreSQL Microsoft Entra admin.
- Runs idempotent SQL to create app principals and grant DB access.

**How do `prodContainerAppPublicWebUrl` and `devContainerAppPublicWebUrl` work with default and custom domains?**

- With ingress enabled, Azure Container Apps provides each app a default FQDN. This template uses that generated URL when `prodContainerAppPublicWebUrl` or `devContainerAppPublicWebUrl` are empty.
- You can also see those generated hostnames in deployment outputs: `prodAppFqdn` and `devAppFqdn`.
- See [Container Apps ingress][aca-ingress] and [built-in environment variables][aca-env-vars] (`CONTAINER_APP_NAME` + `CONTAINER_APP_ENV_DNS_SUFFIX`) for how the default URL is formed.
- If you configure a [custom domain][aca-custom-domains] in the Container App (Portal: Ingress > Custom domains), set the matching `prodContainerAppPublicWebUrl` / `devContainerAppPublicWebUrl` to that custom HTTPS origin and redeploy.
- If you change `ADE_PUBLIC_WEB_URL` directly in the portal, Azure creates a new revision for the app config change. See [environment variables][aca-env-vars].

**Is it safe to re-run deployments?**

- Yes. ARM incremental mode and idempotent SQL make repeated runs safe.
- Use `az deployment group what-if` to preview changes first.

**How do I do PostgreSQL Microsoft Entra role mapping manually?**

If the bootstrap script cannot reach PostgreSQL due to your networking policy, run manual SQL:

```bash
az postgres flexible-server execute \
  --name "<POSTGRES_SERVER_NAME>" \
  --admin-user "<POSTGRES_ENTRA_ADMIN_PRINCIPAL_NAME>" \
  --admin-password "$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)" \
  --database-name postgres \
  --querytext "DO \$\$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '<PROD_APP_NAME>') THEN PERFORM pg_catalog.pgaadauth_create_principal_with_oid('<PROD_APP_NAME>', '<PROD_APP_OBJECT_ID>', 'service', false, false); END IF; END \$\$; GRANT CONNECT, CREATE, TEMP ON DATABASE \"<PROD_DB_NAME>\" TO \"<PROD_APP_NAME>\";"
```

[bicep-overview]: https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/overview
[arm-deployment-modes]: https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/deployment-modes
[arm-what-if]: https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/deploy-what-if
[cidr]: https://learn.microsoft.com/en-us/azure/virtual-network/manage-virtual-network
[pg-firewall]: https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-firewall-rules
[pg-auth]: https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-authentication
[storage-ip-rules]: https://learn.microsoft.com/en-us/azure/storage/common/storage-network-security-ip-address-range
[storage-auth]: https://learn.microsoft.com/en-us/azure/storage/common/authorize-data-access
[aca-replicas]: https://learn.microsoft.com/en-us/azure/container-apps/scale-app
[aca-mi]: https://learn.microsoft.com/en-us/azure/container-apps/managed-identity
[aca-ingress]: https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview
[aca-custom-domains]: https://learn.microsoft.com/en-us/azure/container-apps/custom-domains-managed-certificates
[aca-env-vars]: https://learn.microsoft.com/en-us/azure/container-apps/environment-variables
[rbac-propagation]: https://learn.microsoft.com/en-us/azure/role-based-access-control/troubleshooting#symptom---role-assignment-changes-are-not-being-detected
