# Azure Infra Bicep Reference

## Source Files

- `infra/main.bicep`

## Scenario Matrix

| Scenario | `deployDev` | Deploys |
| --- | --- | --- |
| Prod only | `false` | shared infra + prod app |
| Prod + Dev | `true` | shared infra + prod app + dev app |

## Naming Convention (CAF)

Token shape for hyphen-capable resources:

`<abbr>-<workload>-<env>-<region>-<instance>`

Defaults:

- `workload=ade`
- `env in {shared, prod, dev}`
- `instance=001`

Abbreviations used:

- `rg`: resource group
- `vnet`: virtual network
- `snet`: subnet
- `cae`: container apps environment
- `ca`: container app
- `st`: storage account
- `log`: log analytics workspace
- `psql`: PostgreSQL flexible server

Examples:

- `rg-ade-shared-canadacentral-001`
- `vnet-ade-shared-canadacentral-001`
- `ca-ade-prod-canadacentral-001`
- `psql-ade-shared-canadacentral-001-<hash>`
- `st<hash>` (storage account names are lowercase alphanumeric only)

## Core Parameters

Required for CLI deployments:

- `postgresAdminPassword` (secure)
- `postgresEntraAdminObjectId`
- `postgresEntraAdminPrincipalName`
- `prodImage`, `prodWebUrl`, `prodSecretKey` (secure)
- `devImage`, `devWebUrl`, `devSecretKey` (secure) for prod+dev

Frequently adjusted:

- `location`
- `allowedPublicIpAddresses`
- `postgresSkuName`, `postgresStorageSizeGb`
- `prodMinReplicas`, `prodMaxReplicas`, `devMinReplicas`, `devMaxReplicas`

## Parameter Order (logical)

Deployment scope:

- `location`
- `deployDev`
- `workload`
- `instance`

Networking:

- `vnetCidr`
- `acaSubnetCidr`

PostgreSQL core:

- `postgresAdminUser`
- `postgresAdminPassword`
- `postgresVersion`
- `postgresTier`
- `postgresSkuName`
- `postgresStorageSizeGb`
- `postgresProdDb`
- `postgresDevDb`

PostgreSQL access:

- `postgresEntraAdminObjectId`
- `postgresEntraAdminPrincipalName`
- `postgresEntraAdminPrincipalType`
- `enablePostgresAllowAzureServicesRule`
- `allowedPublicIpAddresses`

Storage:

- `storageSku`

Application config:

- `prodImage`
- `devImage`
- `prodWebUrl`
- `devWebUrl`
- `prodSecretKey`
- `devSecretKey`
- `databaseAuthMode`

Scaling:

- `prodMinReplicas`
- `prodMaxReplicas`
- `devMinReplicas`
- `devMaxReplicas`

## Secure Values Checklist

1. Replace placeholder passwords/secrets before deploy.
2. Never commit real credentials or tenant-specific IDs.
3. Keep production secrets in your secret manager.
4. Confirm `allowedPublicIpAddresses` includes your current deploy runner IP.
5. If passing secure values inline in CLI, avoid shell history leakage.

## Access Behavior (when IP list is empty)

- `allowedPublicIpAddresses=[]` creates no explicit public IP rules in PostgreSQL or Storage.
- If `enablePostgresAllowAzureServicesRule=true` (default), PostgreSQL still includes the `0.0.0.0` `allow-azure-services` rule.
- With `allowedPublicIpAddresses=[]` and `enablePostgresAllowAzureServicesRule=true`, PostgreSQL is reachable from Azure services but not opened to all public Internet IPv4 addresses.
- If `enablePostgresAllowAzureServicesRule=false`, PostgreSQL allows only explicitly listed IP addresses.
- Storage keeps `defaultAction=Deny` and still allows the ACA subnet via virtual network rule.
