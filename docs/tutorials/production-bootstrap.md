# Production Bootstrap (Azure Container Apps, Single Container)

## Goal

Deploy ADE to Azure Container Apps as one container app that runs `api`, `worker`, and `web`, with production-safe networking.

## What You Are Building

- one Azure Container Apps environment in your VNet
- one ADE container app (`ADE_SERVICES=api,worker,web`)
- one Azure Database for PostgreSQL Flexible Server
- one Azure Storage account with:
  - blob container for ADE objects
  - Azure Files share mounted to `/backend/data`

## Choose Your Network Profile

| Profile | Cost | Pattern | Recommended for |
| --- | --- | --- | --- |
| **A. Public endpoints + strict allowlists** | lower | DB/Storage keep public endpoints; only approved IPs/subnets are allowed | most teams starting production |
| **B. Private endpoints (Private Link)** | higher | DB/Storage use private endpoints and private DNS | stricter isolation requirements |

This tutorial implements **Profile A** and includes a hardening path to Profile B.

## Direct Answer: "Can I just add my devices to the VNet instead of using Private Link?"

- Not directly. Devices are not attached to Azure VNets like Azure resources.
- Devices can reach a VNet through **Point-to-Site VPN** or **ExpressRoute**.
- For Azure Storage service endpoints, on-prem/device traffic still needs public NAT IP allowlists.

## Prerequisites

- Azure CLI logged in with permission to create networking, ACA, PostgreSQL, and Storage resources
- ADE image tag (for example `ghcr.io/<org>/<repo>:vX.Y.Z`)
- public HTTPS URL for ADE (for example `https://ade.example.com`)

## Step 1: Set Variables

```bash
az login
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
MY_IP=$(curl -s https://api.ipify.org)

RG=ade-prod-rg
LOCATION=canadacentral

VNET_NAME=ade-vnet
ACA_SUBNET=aca-subnet

ACA_ENV=ade-prod-env
APP_NAME=ade-app
IMAGE=ghcr.io/<org>/<repo>:vX.Y.Z
WEB_URL=https://ade.example.com

PG_SERVER=adepg$RANDOM
PG_ADMIN=adeadmin
PG_PASSWORD='<strong-password>'
PG_DB=ade

STORAGE_ACCOUNT=adestore$RANDOM
BLOB_CONTAINER=ade
FILE_SHARE=ade-data
STORAGE_MOUNT_NAME=adedata

ADE_SECRET_KEY='<long-random-secret-32-bytes-or-more>'
```

## Step 2: Create Resource Group, VNet, and ACA Subnet

```bash
az group create --name "$RG" --location "$LOCATION"

az network vnet create \
  --resource-group "$RG" \
  --name "$VNET_NAME" \
  --location "$LOCATION" \
  --address-prefixes 10.80.0.0/16 \
  --subnet-name "$ACA_SUBNET" \
  --subnet-prefixes 10.80.0.0/23

az network vnet subnet update \
  --resource-group "$RG" \
  --vnet-name "$VNET_NAME" \
  --name "$ACA_SUBNET" \
  --delegations Microsoft.App/environments
```

## Step 3: Create Container Apps Environment in the VNet

```bash
ACA_SUBNET_ID=$(az network vnet subnet show \
  --resource-group "$RG" \
  --vnet-name "$VNET_NAME" \
  --name "$ACA_SUBNET" \
  --query id -o tsv)

az containerapp env create \
  --name "$ACA_ENV" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --infrastructure-subnet-resource-id "$ACA_SUBNET_ID"
```

## Step 4: Create PostgreSQL (Public Endpoint + Firewall Rules)

```bash
az postgres flexible-server create \
  --resource-group "$RG" \
  --name "$PG_SERVER" \
  --location "$LOCATION" \
  --admin-user "$PG_ADMIN" \
  --admin-password "$PG_PASSWORD" \
  --public-access "$MY_IP"

az postgres flexible-server db create \
  --resource-group "$RG" \
  --server-name "$PG_SERVER" \
  --database-name "$PG_DB"

PG_FQDN=$(az postgres flexible-server show \
  --resource-group "$RG" \
  --name "$PG_SERVER" \
  --query fullyQualifiedDomainName -o tsv)

ADE_DATABASE_URL="postgresql+psycopg://${PG_ADMIN}:${PG_PASSWORD}@${PG_FQDN}:5432/${PG_DB}?sslmode=require"
```

Add a temporary bootstrap rule so the new container app can connect before you tighten to exact egress IPs:

```bash
az postgres flexible-server firewall-rule create \
  --resource-group "$RG" \
  --name "$PG_SERVER" \
  --rule-name bootstrap-azure \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

## Step 5: Create Storage and Lock Networking

Create storage resources:

```bash
az storage account create \
  --resource-group "$RG" \
  --name "$STORAGE_ACCOUNT" \
  --location "$LOCATION" \
  --kind StorageV2 \
  --sku Standard_LRS \
  --allow-blob-public-access false

STORAGE_ACCOUNT_KEY=$(az storage account keys list \
  --resource-group "$RG" \
  --account-name "$STORAGE_ACCOUNT" \
  --query "[0].value" -o tsv)

az storage container create \
  --name "$BLOB_CONTAINER" \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_ACCOUNT_KEY"

az storage share-rm create \
  --resource-group "$RG" \
  --storage-account "$STORAGE_ACCOUNT" \
  --name "$FILE_SHARE" \
  --quota 1024 \
  --enabled-protocols SMB
```

Set default deny and add your operator IP:

```bash
az storage account update \
  --resource-group "$RG" \
  --name "$STORAGE_ACCOUNT" \
  --default-action Deny

az storage account network-rule add \
  --resource-group "$RG" \
  --account-name "$STORAGE_ACCOUNT" \
  --ip-address "$MY_IP"
```

Enable Storage service endpoint on ACA subnet and allow that subnet:

```bash
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
```

Why both rules are needed:

- Operator/CI access uses IP allowlists.
- ACA-to-Storage in same region should use VNet rule + service endpoint.
- Storage IP rules do not effectively restrict same-region Azure service traffic.

## Step 6: Register Azure Files Storage in ACA Environment

```bash
az containerapp env storage set \
  --name "$ACA_ENV" \
  --resource-group "$RG" \
  --storage-name "$STORAGE_MOUNT_NAME" \
  --access-mode ReadWrite \
  --azure-file-account-name "$STORAGE_ACCOUNT" \
  --azure-file-account-key "$STORAGE_ACCOUNT_KEY" \
  --azure-file-share-name "$FILE_SHARE"
```

If NSGs are attached to this subnet, allow outbound TCP 445 for Azure Files SMB.

## Step 7: Create the ADE Container App

```bash
az containerapp create \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --environment "$ACA_ENV" \
  --image "$IMAGE" \
  --ingress external \
  --target-port 8000 \
  --min-replicas 1 \
  --max-replicas 2 \
  --secrets \
    ade-database-url="$ADE_DATABASE_URL" \
    ade-secret-key="$ADE_SECRET_KEY" \
  --env-vars \
    ADE_SERVICES=api,worker,web \
    ADE_PUBLIC_WEB_URL="$WEB_URL" \
    ADE_DATABASE_URL=secretref:ade-database-url \
    ADE_SECRET_KEY=secretref:ade-secret-key \
    ADE_BLOB_ACCOUNT_URL="https://${STORAGE_ACCOUNT}.blob.core.windows.net" \
    ADE_BLOB_CONTAINER="$BLOB_CONTAINER" \
    ADE_DATA_DIR=/backend/data \
    ADE_AUTH_DISABLED=false
```

## Step 8: Enable Managed Identity and Blob RBAC

```bash
az containerapp identity assign \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --system-assigned

APP_MI_OBJECT_ID=$(az containerapp identity show \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --query principalId -o tsv)

az role assignment create \
  --assignee-object-id "$APP_MI_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Contributor" \
  --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RG}/providers/Microsoft.Storage/storageAccounts/${STORAGE_ACCOUNT}/blobServices/default/containers/${BLOB_CONTAINER}"
```

## Step 9: Tighten PostgreSQL Firewall to Exact IPs

Get ACA outbound IPs and allow each one:

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

az postgres flexible-server firewall-rule delete \
  --resource-group "$RG" \
  --name "$PG_SERVER" \
  --rule-name bootstrap-azure \
  --yes
```

List final DB rules:

```bash
az postgres flexible-server firewall-rule list \
  --resource-group "$RG" \
  --name "$PG_SERVER" \
  --output table
```

Important:

- ACA outbound IPs can change over time.
- If you need stable egress IPs for strict allowlists, use a workload profiles environment with NAT gateway.

## Step 10: Mount Persistent `/backend/data`

```bash
az containerapp show --name "$APP_NAME" --resource-group "$RG" -o yaml > app.yaml
```

Edit `app.yaml` and add volume mount under `properties.template`:

```yaml
template:
  containers:
    - name: <your-container-name>
      volumeMounts:
        - volumeName: ade-data
          mountPath: /backend/data
  volumes:
    - name: ade-data
      storageType: AzureFile
      storageName: adedata
```

Apply the update:

```bash
az containerapp update --name "$APP_NAME" --resource-group "$RG" --yaml app.yaml
```

## Step 11: Verify

```bash
FQDN=$(az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --query properties.configuration.ingress.fqdn -o tsv)

curl -sS "https://${FQDN}/api/v1/health"
curl -sS "https://${FQDN}/api/v1/info"
az containerapp logs show --name "$APP_NAME" --resource-group "$RG" --tail 200
```

In the UI, confirm:

- sign in works
- upload and run works
- output download works

## Optional Hardening: Move to Private Endpoints (Profile B)

Use private endpoints when your policy requires non-public data-plane access:

- [Use private endpoints for Azure Storage](https://learn.microsoft.com/en-us/azure/storage/common/storage-private-endpoints)
- [Private networking for PostgreSQL Flexible Server](https://learn.microsoft.com/en-us/azure/postgresql/network/concepts-networking-private)

## References

- [Networking in Azure Container Apps environment](https://learn.microsoft.com/en-us/azure/container-apps/networking)
- [Container Apps custom virtual networks](https://learn.microsoft.com/en-us/azure/container-apps/custom-virtual-networks)
- [Managed identities in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity)
- [Use storage mounts in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts)
- [Tutorial: Create an Azure Files volume mount in Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts-azure-files)
- [PostgreSQL networking: public access](https://learn.microsoft.com/en-us/azure/postgresql/network/concepts-networking-public)
- [Enable public access (PostgreSQL Flexible Server)](https://learn.microsoft.com/en-us/azure/postgresql/network/how-to-networking-servers-deployed-public-access-enable-public-access)
- [PostgreSQL firewall rules](https://learn.microsoft.com/en-us/azure/postgresql/security/security-firewall-rules)
- [Storage firewall and virtual network rules](https://learn.microsoft.com/en-us/azure/storage/common/storage-network-security)
- [Storage firewall limitations](https://learn.microsoft.com/en-us/azure/storage/common/storage-network-security-limitations)
- [Create an IP network rule for Azure Storage](https://learn.microsoft.com/en-us/azure/storage/common/storage-network-security-ip-address-range)
- [Create a virtual network rule for Azure Storage](https://learn.microsoft.com/en-us/azure/storage/common/storage-network-security-virtual-networks)
- [Service endpoints overview](https://learn.microsoft.com/en-us/azure/virtual-network/virtual-network-service-endpoints-overview)
- [Point-to-Site VPN](https://learn.microsoft.com/en-us/azure/vpn-gateway/point-to-site-about)
