# ADE Azure Infra (Bicep)

This repo deploys Azure infrastructure from a single template: `infra/main.bicep`.

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

Full runnable command (all parameters, quick-start auth mode = `password`):

```bash
az login
az account set --subscription "<SUBSCRIPTION_ID>"

RESOURCE_GROUP="rg-ade-shared-canadacentral-001"
LOCATION="canadacentral"
OID=$(az ad signed-in-user show --query id -o tsv)
UPN=$(az ad signed-in-user show --query userPrincipalName -o tsv)

az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name "ade-prod" \
  --template-file infra/main.bicep \
  --parameters \
    location="$LOCATION" \
    deployDev=false \
    workload="ade" \
    instance="001" \
    vnetCidr="10.80.0.0/16" \
    acaSubnetCidr="10.80.0.0/23" \
    postgresAdminUser="adeadmin" \
    postgresAdminPassword="<postgres_admin_password>" \
    postgresVersion="16" \
    postgresTier="Burstable" \
    postgresSkuName="Standard_B1ms" \
    postgresStorageSizeGb=32 \
    postgresProdDb="ade" \
    postgresDevDb="ade_dev" \
    postgresEntraAdminObjectId="$OID" \
    postgresEntraAdminPrincipalName="$UPN" \
    postgresEntraAdminPrincipalType="User" \
    enablePostgresAllowAzureServicesRule=true \
    allowedPublicIpAddresses='["203.0.113.10"]' \
    storageSku="Standard_LRS" \
    prodImage="ghcr.io/clac-ca/automatic-data-extractor:vX.Y.Z" \
    devImage="" \
    prodWebUrl="https://ade.example.com" \
    devWebUrl="" \
    prodSecretKey="<prod_secret_key_32_bytes_min>" \
    devSecretKey="" \
    databaseAuthMode="password" \
    prodMinReplicas=1 \
    prodMaxReplicas=2 \
    devMinReplicas=0 \
    devMaxReplicas=1
```

## Option B: Deploy in Azure (production + dev container apps using shared resources)

Use this when you want separate prod and dev apps (for example, dev runs a different image/tag).

This deploys:

- Shared network and logging resources
- 1 shared Azure Container Apps environment
- 2 container apps (prod + dev)
- 1 PostgreSQL server with prod and dev databases
- 1 Storage account with prod and dev blob containers/file shares

Full runnable command (all parameters, quick-start auth mode = `password`):

```bash
az login
az account set --subscription "<SUBSCRIPTION_ID>"

RESOURCE_GROUP="rg-ade-shared-canadacentral-001"
LOCATION="canadacentral"
OID=$(az ad signed-in-user show --query id -o tsv)
UPN=$(az ad signed-in-user show --query userPrincipalName -o tsv)

az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name "ade-proddev" \
  --template-file infra/main.bicep \
  --parameters \
    location="$LOCATION" \
    deployDev=true \
    workload="ade" \
    instance="001" \
    vnetCidr="10.80.0.0/16" \
    acaSubnetCidr="10.80.0.0/23" \
    postgresAdminUser="adeadmin" \
    postgresAdminPassword="<postgres_admin_password>" \
    postgresVersion="16" \
    postgresTier="Burstable" \
    postgresSkuName="Standard_B1ms" \
    postgresStorageSizeGb=32 \
    postgresProdDb="ade" \
    postgresDevDb="ade_dev" \
    postgresEntraAdminObjectId="$OID" \
    postgresEntraAdminPrincipalName="$UPN" \
    postgresEntraAdminPrincipalType="User" \
    enablePostgresAllowAzureServicesRule=true \
    allowedPublicIpAddresses='["203.0.113.10"]' \
    storageSku="Standard_LRS" \
    prodImage="ghcr.io/clac-ca/automatic-data-extractor:vX.Y.Z" \
    devImage="ghcr.io/clac-ca/automatic-data-extractor:vX.Y.Z" \
    prodWebUrl="https://ade.example.com" \
    devWebUrl="https://ade-dev.example.com" \
    prodSecretKey="<prod_secret_key_32_bytes_min>" \
    devSecretKey="<dev_secret_key_32_bytes_min>" \
    databaseAuthMode="password" \
    prodMinReplicas=1 \
    prodMaxReplicas=2 \
    devMinReplicas=0 \
    devMaxReplicas=1
```

Tip:

- Swap `create` with `what-if` to preview changes:
  - `az deployment group what-if ...`

## Parameter Reference

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `location` | `string` | No | Resource group location | Azure region where resources are deployed. |
| `deployDev` | `bool` | No | `false` | `false` = prod app only, `true` = prod + dev apps. |
| `workload` | `string` | No | `ade` | Naming token used in resource names. |
| `instance` | `string` | No | `001` | Naming token for instance/environment numbering. |
| `vnetCidr` | `string` | No | `10.80.0.0/16` | Shared VNet address space in [CIDR notation][cidr]. |
| `acaSubnetCidr` | `string` | No | `10.80.0.0/23` | Container Apps subnet address space in [CIDR notation][cidr]. |
| `postgresAdminUser` | `string` | No | `adeadmin` | PostgreSQL local admin username. Used by quick-start `password` mode. |
| `postgresAdminPassword` | `secure string` | Yes | None | PostgreSQL local admin password. Used by quick-start `password` mode. |
| `postgresVersion` | `string` | No | `16` | PostgreSQL major version. |
| `postgresTier` | `string` | No | `Burstable` | PostgreSQL compute tier. |
| `postgresSkuName` | `string` | No | `Standard_B1ms` | PostgreSQL SKU size (compute/memory class). |
| `postgresStorageSizeGb` | `int` | No | `32` | PostgreSQL storage size in GiB (minimum 32). |
| `postgresProdDb` | `string` | No | `ade` | Name of the production database. |
| `postgresDevDb` | `string` | No | `ade_dev` | Name of the dev database (used when `deployDev=true`). |
| `postgresEntraAdminObjectId` | `string` | Yes | None | Entra object ID configured as PostgreSQL Entra admin. |
| `postgresEntraAdminPrincipalName` | `string` | Yes | None | Entra principal name configured as PostgreSQL Entra admin. |
| `postgresEntraAdminPrincipalType` | `string` | No | `User` | Entra principal type: `User`, `Group`, `ServicePrincipal`. |
| `enablePostgresAllowAzureServicesRule` | `bool` | No | `true` | Adds PostgreSQL `0.0.0.0` firewall rule ("Allow public access from any Azure service within Azure to this server"). See [PostgreSQL firewall rules][pg-firewall]. |
| `allowedPublicIpAddresses` | `array` | No | `[]` | Public IPv4 allowlist for PostgreSQL and Storage firewall/network rules. Empty means no explicit public IP allow rules. See [PostgreSQL firewall rules][pg-firewall] and [Storage IP rules][storage-ip-rules]. |
| `storageSku` | `string` | No | `Standard_LRS` | Storage redundancy/SKU. |
| `prodImage` | `string` | Yes | None | Container image for production app. |
| `devImage` | `string` | No | `''` | Container image for dev app. Empty means use `prodImage`. |
| `prodWebUrl` | `string` | Yes | None | Public HTTPS URL users open for production. |
| `devWebUrl` | `string` | No | `''` | Public HTTPS URL for dev. Empty means use `prodWebUrl`. |
| `prodSecretKey` | `secure string` | Yes | None | ADE app secret key for production (32+ bytes). |
| `devSecretKey` | `secure string` | No | `''` | ADE app secret key for dev. Empty means use `prodSecretKey`. |
| `databaseAuthMode` | `string` | No | `managed_identity` | `password` (quick start) or `managed_identity` (recommended). See [Managed identities in ACA][aca-mi]. |
| `prodMinReplicas` | `int` | No | `1` | Minimum number of production [replicas][aca-replicas]. A replica is one running app instance. |
| `prodMaxReplicas` | `int` | No | `2` | Maximum number of production [replicas][aca-replicas]. |
| `devMinReplicas` | `int` | No | `0` | Minimum number of dev [replicas][aca-replicas]. |
| `devMaxReplicas` | `int` | No | `1` | Maximum number of dev [replicas][aca-replicas]. |

## Managed Identity Mode (Recommended)

### What Is It?

Managed identity lets the app authenticate to Azure services without storing long-lived passwords in app config.
Azure issues short-lived tokens for the app identity.

### Why Is It Recommended?

- No database password in app connection strings
- Short-lived token-based auth
- Better operational security for production

See [Managed identities in ACA][aca-mi].

### Use Managed Identity At Creation Time

Start from Option A or Option B command and change:

- `databaseAuthMode="managed_identity"`

Then run the SQL role-mapping step below.

### Switch An Existing Deployment To Managed Identity

1. Re-run your existing deployment command with:
   - `databaseAuthMode="managed_identity"`
2. Run the SQL role-mapping step below.

### SQL Role-Mapping Step (required for managed identity mode)

```bash
RG="<RESOURCE_GROUP>"
DEPLOYMENT="ade-prod"
PG_ADMIN_UPN="<postgres_entra_admin_principal_name>"

POSTGRES_FQDN=$(az deployment group show --resource-group "$RG" --name "$DEPLOYMENT" --query properties.outputs.postgresFqdn.value -o tsv)
POSTGRES_PROD_DB=$(az deployment group show --resource-group "$RG" --name "$DEPLOYMENT" --query properties.outputs.postgresProdDb.value -o tsv)
PROD_APP_NAME=$(az deployment group show --resource-group "$RG" --name "$DEPLOYMENT" --query properties.outputs.prodAppName.value -o tsv)
PROD_APP_OID=$(az deployment group show --resource-group "$RG" --name "$DEPLOYMENT" --query properties.outputs.prodAppPrincipalId.value -o tsv)
PG_TOKEN=$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)

PGPASSWORD="$PG_TOKEN" psql "host=$POSTGRES_FQDN port=5432 dbname=postgres user=$PG_ADMIN_UPN sslmode=require" <<SQL
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${PROD_APP_NAME}') THEN
    PERFORM pgaadauth_create_principal_with_oid('${PROD_APP_NAME}', '${PROD_APP_OID}', 'service', false, false);
  END IF;
END
$$;
GRANT CONNECT, CREATE, TEMP ON DATABASE "${POSTGRES_PROD_DB}" TO "${PROD_APP_NAME}";
SQL
```

For `deployDev=true`, repeat for `devAppName`, `devAppPrincipalId`, and `postgresDevDb` outputs.

## Teardown

```bash
az group delete --name "<RESOURCE_GROUP>" --yes --no-wait
```

[bicep-overview]: https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/overview
[arm-deployment-modes]: https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/deployment-modes
[arm-what-if]: https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/deploy-what-if
[cidr]: https://learn.microsoft.com/en-us/azure/virtual-network/manage-virtual-network
[pg-firewall]: https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-firewall-rules
[storage-ip-rules]: https://learn.microsoft.com/en-us/azure/storage/common/storage-network-security-ip-address-range
[aca-replicas]: https://learn.microsoft.com/en-us/azure/container-apps/scale-app
[aca-mi]: https://learn.microsoft.com/en-us/azure/container-apps/managed-identity
