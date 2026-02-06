# Deploy to Production (Azure Container Apps)

## Goal

Deploy ADE on Azure Container Apps with one of two validated network patterns:

- **Guide A (recommended):** public endpoints + strict allowlists
- **Guide B (more isolated):** private-only endpoints

Both guides run ADE in one container app (`api,worker,web`) and keep `/backend/data` persisted.

## Choose One Guide

| Guide | Choose this when | External direct access to DB/Storage |
| --- | --- | --- |
| **A. Public + strict allowlists** | You want secure defaults and still need access from selected public IPs | **Yes**, via explicit IP allowlists |
| **B. Private-only endpoints** | You want stronger network isolation and private-only data plane | **No**, use VPN/ExpressRoute (or jump VM) |

Important: PostgreSQL networking mode (public vs private) is effectively a build-time choice. Plan for server re-creation if you switch guides later.

## Shared Prerequisites

- Azure Container App already running ADE (`ADE_SERVICES=api,worker,web`)
- managed identity configured on the app
- Azure Files mounted to `/backend/data`
- `ADE_DATABASE_URL` set with `sslmode=require`
- `ADE_BLOB_ACCOUNT_URL` + `ADE_BLOB_CONTAINER` configured

Set base variables:

```bash
RG=<resource-group>
APP_NAME=ade-app
PG_SERVER=<postgres-server>
STORAGE_ACCOUNT=<storage-account>
WEB_URL=https://ade.example.com
IMAGE=ghcr.io/<org>/<repo>:vX.Y.Z
LOCATION=<azure-region>
```

## Guide A: Public Endpoints + Strict Allowlists

### A1) Define approved external IPs

```bash
IP1=203.0.113.10
IP2=198.51.100.20
```

Use real public egress IPs (office, VPN egress, CI runner).

### A2) Lock PostgreSQL with firewall rules

Add approved external IPs:

```bash
az postgres flexible-server firewall-rule create \
  --resource-group "$RG" \
  --name "$PG_SERVER" \
  --rule-name office-1 \
  --start-ip-address "$IP1" \
  --end-ip-address "$IP1"

az postgres flexible-server firewall-rule create \
  --resource-group "$RG" \
  --name "$PG_SERVER" \
  --rule-name office-2 \
  --start-ip-address "$IP2" \
  --end-ip-address "$IP2"
```

Add ACA outbound IPs so the app can reach PostgreSQL:

```bash
ACA_EGRESS_IPS=$(az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --query properties.outboundIpAddresses \
  -o tsv | tr ',' '\n')

i=1
for ip in $ACA_EGRESS_IPS; do
  az postgres flexible-server firewall-rule create \
    --resource-group "$RG" \
    --name "$PG_SERVER" \
    --rule-name "aca-egress-$i" \
    --start-ip-address "$ip" \
    --end-ip-address "$ip"
  i=$((i+1))
done

az postgres flexible-server firewall-rule list \
  --resource-group "$RG" \
  --name "$PG_SERVER" \
  --output table
```

Important:

- Do not keep broad `0.0.0.0` rules after bootstrap.
- Recheck ACA outbound IPs after network/environment changes.
- If you need stable egress IP, use NAT Gateway with a workload profiles environment.

### A3) Lock Storage with default deny + IP/VNet rules

Ensure public access is enabled for allowlist mode, then deny by default:

```bash
az storage account update \
  --resource-group "$RG" \
  --name "$STORAGE_ACCOUNT" \
  --public-network-access Enabled \
  --default-action Deny
```

Allow approved external IPs:

```bash
az storage account network-rule add \
  --resource-group "$RG" \
  --account-name "$STORAGE_ACCOUNT" \
  --ip-address "$IP1"

az storage account network-rule add \
  --resource-group "$RG" \
  --account-name "$STORAGE_ACCOUNT" \
  --ip-address "$IP2"
```

Allow ACA subnet using service endpoint + VNet rule:

```bash
VNET_NAME=<vnet-name>
ACA_SUBNET=<aca-subnet-name>

az network vnet subnet update \
  --resource-group "$RG" \
  --vnet-name "$VNET_NAME" \
  --name "$ACA_SUBNET" \
  --service-endpoints Microsoft.Storage

ACA_SUBNET_ID=$(az network vnet subnet show \
  --resource-group "$RG" \
  --vnet-name "$VNET_NAME" \
  --name "$ACA_SUBNET" \
  --query id -o tsv)

az storage account network-rule add \
  --resource-group "$RG" \
  --account-name "$STORAGE_ACCOUNT" \
  --subnet "$ACA_SUBNET_ID"

az storage account network-rule list \
  --resource-group "$RG" \
  --account-name "$STORAGE_ACCOUNT" \
  -o json
```

Important:

- Storage IP rules alone are not sufficient for same-region Azure services.
- Keep the ACA subnet VNet rule in place.

### A4) Deploy and verify

```bash
az containerapp exec \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --command "ade db migrate"

az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --image "$IMAGE"

curl -sS "$WEB_URL/api/v1/health"
curl -sS "$WEB_URL/api/v1/info"
az containerapp logs show --name "$APP_NAME" --resource-group "$RG" --tail 200
```

## Guide B: Private-Only Endpoints

Use this when you want no direct public access to database/storage.

### B1) Create PostgreSQL in private access mode

Create (or reuse) a delegated PostgreSQL subnet and private DNS zone:

```bash
VNET_NAME=<vnet-name>
PG_SUBNET=<postgres-subnet>
PG_PRIVATE_DNS_ZONE=<name>.private.postgres.database.azure.com

az network vnet subnet create \
  --resource-group "$RG" \
  --vnet-name "$VNET_NAME" \
  --name "$PG_SUBNET" \
  --address-prefixes 10.80.10.0/24 \
  --delegations Microsoft.DBforPostgreSQL/flexibleServers

az network private-dns zone create \
  --resource-group "$RG" \
  --name "$PG_PRIVATE_DNS_ZONE"

az network private-dns link vnet create \
  --resource-group "$RG" \
  --zone-name "$PG_PRIVATE_DNS_ZONE" \
  --name pg-dns-link \
  --virtual-network "$VNET_NAME" \
  --registration-enabled false
```

Create PostgreSQL Flexible Server with private networking:

```bash
PG_SERVER=<postgres-server>
PG_ADMIN=adeadmin
PG_PASSWORD='<strong-password>'

az postgres flexible-server create \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --name "$PG_SERVER" \
  --admin-user "$PG_ADMIN" \
  --admin-password "$PG_PASSWORD" \
  --vnet "$VNET_NAME" \
  --subnet "$PG_SUBNET" \
  --private-dns-zone "$PG_PRIVATE_DNS_ZONE"
```

### B2) Create private endpoints for Storage blob + file

Create a subnet for private endpoints:

```bash
PE_SUBNET=<private-endpoints-subnet>

az network vnet subnet create \
  --resource-group "$RG" \
  --vnet-name "$VNET_NAME" \
  --name "$PE_SUBNET" \
  --address-prefixes 10.80.20.0/24

az network vnet subnet update \
  --resource-group "$RG" \
  --vnet-name "$VNET_NAME" \
  --name "$PE_SUBNET" \
  --disable-private-endpoint-network-policies true
```

Create private DNS zones and link to VNet:

```bash
az network private-dns zone create -g "$RG" -n privatelink.blob.core.windows.net
az network private-dns zone create -g "$RG" -n privatelink.file.core.windows.net

az network private-dns link vnet create -g "$RG" -n blob-dns-link \
  -z privatelink.blob.core.windows.net -v "$VNET_NAME" -e false
az network private-dns link vnet create -g "$RG" -n file-dns-link \
  -z privatelink.file.core.windows.net -v "$VNET_NAME" -e false
```

Create private endpoints:

```bash
STORAGE_ID=$(az storage account show -g "$RG" -n "$STORAGE_ACCOUNT" --query id -o tsv)

az network private-endpoint create \
  --resource-group "$RG" \
  --name "${STORAGE_ACCOUNT}-blob-pe" \
  --vnet-name "$VNET_NAME" \
  --subnet "$PE_SUBNET" \
  --private-connection-resource-id "$STORAGE_ID" \
  --group-id blob \
  --connection-name "${STORAGE_ACCOUNT}-blob-conn"

az network private-endpoint create \
  --resource-group "$RG" \
  --name "${STORAGE_ACCOUNT}-file-pe" \
  --vnet-name "$VNET_NAME" \
  --subnet "$PE_SUBNET" \
  --private-connection-resource-id "$STORAGE_ID" \
  --group-id file \
  --connection-name "${STORAGE_ACCOUNT}-file-conn"
```

Attach private DNS zones to each private endpoint:

```bash
BLOB_DNS_ZONE_ID=$(az network private-dns zone show -g "$RG" -n privatelink.blob.core.windows.net --query id -o tsv)
FILE_DNS_ZONE_ID=$(az network private-dns zone show -g "$RG" -n privatelink.file.core.windows.net --query id -o tsv)

az network private-endpoint dns-zone-group create \
  --resource-group "$RG" \
  --endpoint-name "${STORAGE_ACCOUNT}-blob-pe" \
  --name default \
  --private-dns-zone "$BLOB_DNS_ZONE_ID" \
  --zone-name privatelink.blob.core.windows.net

az network private-endpoint dns-zone-group create \
  --resource-group "$RG" \
  --endpoint-name "${STORAGE_ACCOUNT}-file-pe" \
  --name default \
  --private-dns-zone "$FILE_DNS_ZONE_ID" \
  --zone-name privatelink.file.core.windows.net
```

Disable storage public endpoint:

```bash
az storage account update \
  --resource-group "$RG" \
  --name "$STORAGE_ACCOUNT" \
  --public-network-access Disabled
```

### B3) External access model for private-only

You do not allow direct public IP access to DB/Storage.

Use one of these:

- Point-to-Site or Site-to-Site VPN into the VNet
- ExpressRoute private peering
- Bastion to a jump VM in the VNet, then access private endpoints from that VM

### B4) Deploy and verify

```bash
az containerapp exec \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --command "ade db migrate"

az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --image "$IMAGE"

curl -sS "$WEB_URL/api/v1/health"
curl -sS "$WEB_URL/api/v1/info"
az containerapp logs show --name "$APP_NAME" --resource-group "$RG" --tail 200
```

## Roll Back (Both Guides)

```bash
PREV_IMAGE=ghcr.io/<org>/<repo>:<previous-tag>
az containerapp update --name "$APP_NAME" --resource-group "$RG" --image "$PREV_IMAGE"
```

## Validation Checklist

- health/info endpoints return success
- app logs show API + worker + web healthy
- upload, run, and output download succeed
- network rules match chosen guide only (no mixed half-config)

## References (Microsoft Learn)

- [Azure Container Apps virtual network configuration](https://learn.microsoft.com/en-us/azure/container-apps/custom-virtual-networks)
- [PostgreSQL public networking](https://learn.microsoft.com/en-us/azure/postgresql/network/concepts-networking-public)
- [PostgreSQL firewall rules](https://learn.microsoft.com/en-us/azure/postgresql/security/security-firewall-rules)
- [PostgreSQL private networking](https://learn.microsoft.com/en-us/azure/postgresql/network/concepts-networking-private)
- [PostgreSQL private link networking](https://learn.microsoft.com/en-us/azure/postgresql/network/concepts-networking-private-link)
- [PostgreSQL networking operations by mode](https://learn.microsoft.com/en-us/azure/postgresql/network/how-to-networking)
- [Storage firewall rules](https://learn.microsoft.com/en-us/azure/storage/common/storage-network-security)
- [Storage virtual network rules](https://learn.microsoft.com/en-us/azure/storage/common/storage-network-security-virtual-networks)
- [Storage firewall limitations](https://learn.microsoft.com/en-us/azure/storage/common/storage-network-security-limitations)
- [Storage private endpoints](https://learn.microsoft.com/en-us/azure/storage/common/storage-private-endpoints)
- [Private Endpoint DNS zone values](https://learn.microsoft.com/en-us/azure/private-link/private-endpoint-dns)
- [Azure Bastion overview](https://learn.microsoft.com/en-us/azure/bastion/bastion-overview)
- [About Point-to-Site VPN](https://learn.microsoft.com/en-us/azure/vpn-gateway/point-to-site-about)
- [Azure CLI: `az postgres flexible-server`](https://learn.microsoft.com/en-us/cli/azure/postgres/flexible-server?view=azure-cli-latest)
- [Azure CLI: `az postgres flexible-server firewall-rule`](https://learn.microsoft.com/en-us/cli/azure/postgres/flexible-server/firewall-rule?view=azure-cli-latest)
- [Azure CLI: `az storage account network-rule`](https://learn.microsoft.com/en-us/cli/azure/storage/account/network-rule?view=azure-cli-latest)
- [Azure CLI: `az network private-endpoint`](https://learn.microsoft.com/en-us/cli/azure/network/private-endpoint?view=azure-cli-latest)
- [Azure CLI: `az network private-endpoint dns-zone-group`](https://learn.microsoft.com/en-us/cli/azure/network/private-endpoint/dns-zone-group?view=azure-cli-latest)
