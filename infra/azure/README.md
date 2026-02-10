# ADE Azure Infra (Bicep)

This folder contains the Azure infrastructure-as-code for ADE.

- Template entrypoint: `infra/azure/main.bicep`
- Domain modules: `infra/azure/modules/*.bicep`
- PostgreSQL Entra bootstrap script: `infra/azure/scripts/postgresql-entra-bootstrap.sh`

## What Is Azure Bicep?

Azure Bicep is Microsoft's infrastructure-as-code language for Azure Resource Manager (ARM). You declare resources in code, and Azure creates or updates them to match the template.

- Bicep overview: [learn.microsoft.com/azure/azure-resource-manager/bicep/overview][bicep-overview]

## Is It Safe To Re-Run?

Yes.

- ARM deployments use incremental mode by default.
- Role assignments use deterministic names (`guid(...)`) to avoid duplicates.
- PostgreSQL Entra bootstrap SQL is idempotent and safe to run again.
- Entra groups created through the Graph Bicep extension are reconciled by `uniqueName`.

Reference: [ARM deployment modes][arm-deployment-modes]

## What This Deploys

Shared platform:
- Virtual Network + delegated Container Apps subnet
- Log Analytics workspace
- Container Apps managed environment
- PostgreSQL Flexible Server + production database (+ optional development database)
- Storage account + production blob container/file share (+ optional development blob container/file share)

Application:
- Production Container App
- Optional development Container App

Access automation:
- Optional Entra group creation from prefix (`createAccessControlEntraGroups=true`)
- Azure RBAC assignments for the access-control groups
- PostgreSQL Entra bootstrap for app managed identities + DB group grants (when PostgreSQL auth mode includes Entra)

## Resource Naming

The template uses deterministic names so re-runs in the same resource group keep the same names while still reducing global-name collisions.

- Shared suffix: first 5 chars of `uniqueString(resourceGroup().id)`
- Storage account pattern: `st<workload><env><region><instance><suffix>`
  - Current shared-environment token is `sh`
  - Region token is the first 3 chars of the location token
- PostgreSQL server pattern: `psql-<workload>-shared-<region>-<instance>-<suffix>`

Example:
- Storage account: `stadeshcan001a1b2c`
- PostgreSQL server: `psql-ade-shared-canadacentral-001-a1b2c`

## Access-Control Model

Group naming contract (derived from `accessControlGroupNamePrefix`):
- `<prefix>-rg-owners`
- `<prefix>-rg-contributors`
- `<prefix>-rg-readers`
- `<prefix>-ca-admins`
- `<prefix>-ca-operators`
- `<prefix>-ca-readers`
- `<prefix>-db-admins`
- `<prefix>-db-readwrite`
- `<prefix>-db-readonly`
- `<prefix>-st-admins`
- `<prefix>-st-readwrite`
- `<prefix>-st-readonly`

### Recommended (simple) mode

Set `createAccessControlEntraGroups=true`.

- The template creates/updates all groups from the prefix.
- The template uses those group object IDs for RBAC and DB grants automatically.
- You do not pass any `*EntraGroupObjectId` parameters.

### Manual mode

Set `createAccessControlEntraGroups=false`.

- You must pass all `*EntraGroupObjectId` parameters explicitly.
- Use this if groups are managed centrally by your identity team.

### Disabled mode (no groups)

Set `createAccessControlEntraGroups=false` and leave all `*EntraGroupObjectId` parameters empty.

- The app and infrastructure still deploy and run.
- Group-based RBAC assignments are skipped.
- Database group grants for `<prefix>-db-readwrite` and `<prefix>-db-readonly` are skipped.

## Prerequisites

- Azure CLI installed (`az`) and signed in.
- Bicep installed via Azure CLI (`az bicep upgrade`).
- Permission to deploy into the target resource group.
- Permission to create role assignments at resource group and resource scopes when access-control groups are enabled.
- If `createAccessControlEntraGroups=true`, identity permissions to create/update Entra groups (for example Graph permissions such as `Group.ReadWrite.All`).

## Option A: Deploy In Azure (Production Only)

This creates one production ADE Container App on shared Azure resources.

If you set `postgresqlAuthenticationMode` to `postgresql_only` or `postgresql_and_microsoft_entra`, also pass:
- `postgresqlAdministratorLogin="<POSTGRESQL_ADMIN_LOGIN>"`
- `postgresqlAdministratorPassword="<POSTGRESQL_ADMIN_PASSWORD>"`

```bash
az login
az account set --subscription "<SUBSCRIPTION_ID>"
az group create --name "rg-ade-shared-canadacentral-001" --location "canadacentral"

az deployment group create \
  --resource-group "rg-ade-shared-canadacentral-001" \
  --name "ade-azure-production-only" \
  --template-file infra/azure/main.bicep \
  --parameters \
    location="canadacentral" \
    workload="ade" \
    instance="001" \
    deployDevelopmentEnvironment=false \
    virtualNetworkAddressPrefix="10.80.0.0/16" \
    containerAppsSubnetAddressPrefix="10.80.0.0/23" \
    postgresqlVersion="16" \
    postgresqlSkuTier="Burstable" \
    postgresqlSkuName="Standard_B1ms" \
    postgresqlStorageSizeGb=32 \
    postgresqlProductionDatabaseName="ade" \
    postgresqlDevelopmentDatabaseName="ade_dev" \
    postgresqlAuthenticationMode="microsoft_entra_only" \
    postgresqlAllowPublicAccessFromAzureServices=true \
    publicIpv4Allowlist='["<ADMIN_PUBLIC_IPV4>"]' \
    storageAccountSkuName="Standard_LRS" \
    storageBlobAuthenticationMethod="microsoft_entra" \
    accessControlGroupNamePrefix="ade" \
    createAccessControlEntraGroups=true \
    productionContainerAppImage="ghcr.io/clac-ca/automatic-data-extractor:<PRODUCTION_TAG>" \
    productionContainerAppPublicWebUrl="" \
    productionContainerAppSecretKey="<ADE_SECRET_KEY>" \
    productionContainerAppEnvironmentOverrides='{"ADE_LOG_LEVEL":"INFO","ADE_LOG_FORMAT":"json"}' \
    productionContainerAppMinimumReplicas=1 \
    productionContainerAppMaximumReplicas=2 \
    developmentContainerAppImage="" \
    developmentContainerAppPublicWebUrl="" \
    developmentContainerAppSecretKey="" \
    developmentContainerAppEnvironmentOverrides='{}' \
    developmentContainerAppMinimumReplicas=0 \
    developmentContainerAppMaximumReplicas=1
```

## Option B: Deploy In Azure (Production + Development)

This creates a production app and a separate development app that share the same platform resources.

```bash
az login
az account set --subscription "<SUBSCRIPTION_ID>"
az group create --name "rg-ade-shared-canadacentral-001" --location "canadacentral"

az deployment group create \
  --resource-group "rg-ade-shared-canadacentral-001" \
  --name "ade-azure-production-and-development" \
  --template-file infra/azure/main.bicep \
  --parameters \
    location="canadacentral" \
    workload="ade" \
    instance="001" \
    deployDevelopmentEnvironment=true \
    virtualNetworkAddressPrefix="10.80.0.0/16" \
    containerAppsSubnetAddressPrefix="10.80.0.0/23" \
    postgresqlVersion="16" \
    postgresqlSkuTier="Burstable" \
    postgresqlSkuName="Standard_B1ms" \
    postgresqlStorageSizeGb=32 \
    postgresqlProductionDatabaseName="ade" \
    postgresqlDevelopmentDatabaseName="ade_dev" \
    postgresqlAuthenticationMode="microsoft_entra_only" \
    postgresqlAllowPublicAccessFromAzureServices=true \
    publicIpv4Allowlist='["<ADMIN_PUBLIC_IPV4>"]' \
    storageAccountSkuName="Standard_LRS" \
    storageBlobAuthenticationMethod="microsoft_entra" \
    accessControlGroupNamePrefix="ade" \
    createAccessControlEntraGroups=true \
    productionContainerAppImage="ghcr.io/clac-ca/automatic-data-extractor:<PRODUCTION_TAG>" \
    productionContainerAppPublicWebUrl="" \
    productionContainerAppSecretKey="<ADE_SECRET_KEY>" \
    productionContainerAppEnvironmentOverrides='{"ADE_LOG_LEVEL":"INFO","ADE_LOG_FORMAT":"json"}' \
    productionContainerAppMinimumReplicas=1 \
    productionContainerAppMaximumReplicas=2 \
    developmentContainerAppImage="ghcr.io/clac-ca/automatic-data-extractor:<DEVELOPMENT_TAG>" \
    developmentContainerAppPublicWebUrl="" \
    developmentContainerAppSecretKey="<ADE_SECRET_KEY_FOR_DEV_OR_EMPTY_TO_REUSE_PRODUCTION>" \
    developmentContainerAppEnvironmentOverrides='{"ADE_LOG_LEVEL":"DEBUG","ADE_LOG_FORMAT":"json"}' \
    developmentContainerAppMinimumReplicas=0 \
    developmentContainerAppMaximumReplicas=1
```

## Parameter Reference

### General + Networking

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `location` | `string` | No | resource group location | Azure region for resources. |
| `workload` | `string` | No | `ade` | Naming token for this workload. |
| `instance` | `string` | No | `001` | Naming token for environment instance. |
| `deployDevelopmentEnvironment` | `bool` | No | `false` | Deploy the optional development app/database/storage resources. |
| `virtualNetworkAddressPrefix` | `string` | No | `10.80.0.0/16` | VNet CIDR range. |
| `containerAppsSubnetAddressPrefix` | `string` | No | `10.80.0.0/23` | Delegated Container Apps subnet CIDR range. |

### PostgreSQL

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `postgresqlAdministratorLogin` | `string` | No | `''` | PostgreSQL password-auth admin login. Only used when auth mode includes password auth. |
| `postgresqlAdministratorPassword` | `secure string` | No | `''` | PostgreSQL password-auth admin password. Required only when auth mode includes password auth. |
| `postgresqlVersion` | `string` | No | `16` | PostgreSQL major version. |
| `postgresqlSkuTier` | `string` | No | `Burstable` | PostgreSQL compute tier. |
| `postgresqlSkuName` | `string` | No | `Standard_B1ms` | PostgreSQL compute SKU. |
| `postgresqlStorageSizeGb` | `int` | No | `32` | PostgreSQL storage size in GiB. |
| `postgresqlProductionDatabaseName` | `string` | No | `ade` | Production database name. |
| `postgresqlDevelopmentDatabaseName` | `string` | No | `ade_dev` | Development database name. |
| `postgresqlAuthenticationMode` | `string` | No | `microsoft_entra_only` | DB auth mode: local password, Entra, or both. |
| `postgresqlAllowPublicAccessFromAzureServices` | `bool` | No | `true` | Adds `0.0.0.0` firewall rule for Azure services access. |
| `publicIpv4Allowlist` | `array` | No | `[]` | Public IPv4 addresses allowed through PostgreSQL and storage firewalls. |

### Storage

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `storageAccountSkuName` | `string` | No | `Standard_LRS` | Storage redundancy/performance SKU. |
| `storageBlobAuthenticationMethod` | `string` | No | `microsoft_entra` | Blob auth method: managed identity (`microsoft_entra`) or shared key (`shared_key`). |

### Access Control

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `accessControlGroupNamePrefix` | `string` | No | `ade` | Prefix used to derive group names and DB principal names. |
| `createAccessControlEntraGroups` | `bool` | No | `true` | When true, creates all access-control groups and auto-wires their object IDs. |
| `resourceGroupOwnersEntraGroupObjectId` | `string` | No | `''` | Optional object ID for `<prefix>-rg-owners` when reusing existing groups. |
| `resourceGroupContributorsEntraGroupObjectId` | `string` | No | `''` | Optional object ID for `<prefix>-rg-contributors` when reusing existing groups. |
| `resourceGroupReadersEntraGroupObjectId` | `string` | No | `''` | Optional object ID for `<prefix>-rg-readers` when reusing existing groups. |
| `containerAppsAdminsEntraGroupObjectId` | `string` | No | `''` | Optional object ID for `<prefix>-ca-admins` when reusing existing groups. |
| `containerAppsOperatorsEntraGroupObjectId` | `string` | No | `''` | Optional object ID for `<prefix>-ca-operators` when reusing existing groups. |
| `containerAppsReadersEntraGroupObjectId` | `string` | No | `''` | Optional object ID for `<prefix>-ca-readers` when reusing existing groups. |
| `databaseAdminsEntraGroupObjectId` | `string` | No | `''` | Optional object ID for `<prefix>-db-admins` Entra admin group. |
| `databaseReadWriteEntraGroupObjectId` | `string` | No | `''` | Optional object ID for `<prefix>-db-readwrite` DB grants group. |
| `databaseReadOnlyEntraGroupObjectId` | `string` | No | `''` | Optional object ID for `<prefix>-db-readonly` DB grants group. |
| `storageAdminsEntraGroupObjectId` | `string` | No | `''` | Optional object ID for `<prefix>-st-admins` when reusing existing groups. |
| `storageReadWriteEntraGroupObjectId` | `string` | No | `''` | Optional object ID for `<prefix>-st-readwrite` when reusing existing groups. |
| `storageReadOnlyEntraGroupObjectId` | `string` | No | `''` | Optional object ID for `<prefix>-st-readonly` when reusing existing groups. |

### Production Container App

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `productionContainerAppImage` | `string` | Yes | none | Production container image URL/tag. |
| `productionContainerAppPublicWebUrl` | `string` | No | `''` | Sets `ADE_PUBLIC_WEB_URL`. Empty uses Container App default HTTPS URL. |
| `productionContainerAppSecretKey` | `secure string` | Yes | none | Sets `ADE_SECRET_KEY` for production app. |
| `productionContainerAppEnvironmentOverrides` | `object` | No | `{}` | Additional production app environment variables. |
| `productionContainerAppMinimumReplicas` | `int` | No | `1` | Minimum running replicas. |
| `productionContainerAppMaximumReplicas` | `int` | No | `2` | Maximum running replicas. |

### Development Container App

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `developmentContainerAppImage` | `string` | No | `''` | Development image. Empty reuses production image. |
| `developmentContainerAppPublicWebUrl` | `string` | No | `''` | Sets `ADE_PUBLIC_WEB_URL`. Empty uses Container App default HTTPS URL. |
| `developmentContainerAppSecretKey` | `secure string` | No | `''` | Development `ADE_SECRET_KEY`. Empty reuses production key. |
| `developmentContainerAppEnvironmentOverrides` | `object` | No | `{}` | Additional development app environment variables. |
| `developmentContainerAppMinimumReplicas` | `int` | No | `0` | Minimum dev replicas. |
| `developmentContainerAppMaximumReplicas` | `int` | No | `1` | Maximum dev replicas. |

## RBAC Mapping

| Group | Scope | Role(s) |
| --- | --- | --- |
| `<prefix>-rg-owners` | Resource group | `Owner` |
| `<prefix>-rg-contributors` | Resource group | `Contributor` |
| `<prefix>-rg-readers` | Resource group | `Reader` |
| `<prefix>-ca-admins` | Prod/dev apps, ACA environment, Log Analytics | `Container Apps Contributor`, `Container Apps ManagedEnvironments Contributor`, `Log Analytics Data Reader` |
| `<prefix>-ca-operators` | Prod/dev apps, ACA environment, Log Analytics | `Container Apps Operator`, `Reader`, `Log Analytics Data Reader` |
| `<prefix>-ca-readers` | Prod/dev apps, ACA environment, Log Analytics | `Reader`, `Log Analytics Data Reader` |
| `<prefix>-db-admins` | PostgreSQL server | `Contributor` |
| `<prefix>-db-readwrite` | PostgreSQL server | `Reader` (control plane visibility) |
| `<prefix>-db-readonly` | PostgreSQL server | `Reader` (control plane visibility) |
| `<prefix>-st-admins` | Storage account | `Storage Account Contributor` |
| `<prefix>-st-readwrite` | Storage account | `Storage Blob Data Contributor` |
| `<prefix>-st-readonly` | Storage account | `Storage Blob Data Reader` |

These role assignments are applied only when all required group object IDs are available (auto-created or provided).

Reference: [Azure built-in roles][azure-built-in-roles]

## PostgreSQL DB Group Grants (Entra)

When `postgresqlAuthenticationMode` includes Entra, the bootstrap module always creates the app managed identity principals and grants app DB access.  
When DB group IDs are available (auto-created or provided), it also creates Entra group principals and applies idempotent grants:

- `<prefix>-db-readwrite`
  - DB: `CONNECT`, `TEMP`
  - Schema `public`: `USAGE`, `CREATE`
  - Tables in `public`: `SELECT, INSERT, UPDATE, DELETE`
  - Sequences in `public`: `USAGE, SELECT, UPDATE`
- `<prefix>-db-readonly`
  - DB: `CONNECT`
  - Schema `public`: `USAGE`
  - Tables in `public`: `SELECT`
  - Sequences in `public`: `SELECT`

## FAQ

**Do I need `postgresqlAdministratorLogin` and `postgresqlAdministratorPassword` with Entra-only auth?**

No. In `postgresqlAuthenticationMode="microsoft_entra_only"`, the template omits password-auth admin properties entirely.  
You only need those parameters when auth mode includes password auth (`postgresql_only` or `postgresql_and_microsoft_entra`).

Reference: [PostgreSQL Flexible Server ARM template reference][postgresql-flexible-servers-template-reference]

**How does the Container App public URL work?**

- If `productionContainerAppPublicWebUrl` / `developmentContainerAppPublicWebUrl` are empty, ADE uses each app's default Container Apps HTTPS URL.
- For a custom domain, add/bind the domain in Azure Container Apps, set the corresponding `*PublicWebUrl` parameter to that HTTPS origin, and redeploy.

References: [Container Apps ingress][container-apps-ingress], [custom domains][container-apps-custom-domains], [environment variables][container-apps-environment-variables]

**What happens with `storageBlobAuthenticationMethod="shared_key"`?**

The template creates a Container Apps secret and sets `ADE_BLOB_CONNECTION_STRING` from the storage account key.

**What happens with `storageBlobAuthenticationMethod="microsoft_entra"`?**

The template sets `ADE_BLOB_ACCOUNT_URL` and assigns blob data contributor role to each deployed app identity for its blob container.

Reference: [Blob authorization with Microsoft Entra ID][blob-entra-authorization]

**What if `createAccessControlEntraGroups=true` but my identity cannot create groups?**

The deployment fails during Graph resource creation. Use `createAccessControlEntraGroups=false` and pass all `*EntraGroupObjectId` parameters.

**Can I run without groups at all?**

Yes. Set `createAccessControlEntraGroups=false` and do not provide any group object IDs. The app still works; only group-based RBAC and DB group grants are skipped.

**Can I use `what-if` for everything?**

- Use `what-if` for ARM resource preview.
- Graph extension resources have limitations and are not fully represented in ARM what-if output.

Reference: [Bicep Graph extension limitations][graph-bicep-limitations]

**How do I validate locally before deploying?**

Run:

```bash
bash infra/azure/validate.sh
```

[bicep-overview]: https://learn.microsoft.com/azure/azure-resource-manager/bicep/overview
[arm-deployment-modes]: https://learn.microsoft.com/azure/azure-resource-manager/templates/deployment-modes
[azure-built-in-roles]: https://learn.microsoft.com/azure/role-based-access-control/built-in-roles
[container-apps-ingress]: https://learn.microsoft.com/azure/container-apps/ingress-overview
[container-apps-custom-domains]: https://learn.microsoft.com/azure/container-apps/custom-domains-certificates
[container-apps-environment-variables]: https://learn.microsoft.com/azure/container-apps/environment-variables
[blob-entra-authorization]: https://learn.microsoft.com/azure/storage/blobs/authorize-access-azure-active-directory
[graph-bicep-limitations]: https://learn.microsoft.com/graph/templates/bicep/overview#known-limitations
[postgresql-flexible-servers-template-reference]: https://learn.microsoft.com/azure/templates/microsoft.dbforpostgresql/flexibleservers
