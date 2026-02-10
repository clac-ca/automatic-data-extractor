# Azure Infra Bicep Reference

## Source Files

- `infra/main.bicep`
- `infra/main.prod.bicepparam`
- `infra/main.proddev.bicepparam`

## Scenario Matrix

| Scenario | Parameters file | `deployDev` | Deploys |
| --- | --- | --- | --- |
| Prod only | `infra/main.prod.bicepparam` | `false` | shared infra + prod app |
| Prod + Dev | `infra/main.proddev.bicepparam` | `true` | shared infra + prod app + dev app |

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

Required in scenario files:

- `postgresAdminPassword` (secure)
- `postgresEntraAdminObjectId`
- `postgresEntraAdminPrincipalName`
- `prodImage`, `prodWebUrl`, `prodSecretKey` (secure)
- `devImage`, `devWebUrl`, `devSecretKey` (secure) for prod+dev

Frequently adjusted:

- `location`
- `operatorIps`
- `postgresSkuName`, `postgresStorageSizeGb`
- `prodMinReplicas`, `prodMaxReplicas`, `devMinReplicas`, `devMaxReplicas`

## Generated Portal Artifacts

- `infra/main.json`
- `infra/main.prod.parameters.json`
- `infra/main.proddev.parameters.json`

Regenerate when source changes:

```bash
az bicep build --file infra/main.bicep --outfile infra/main.json
az bicep build-params --file infra/main.prod.bicepparam --outfile infra/main.prod.parameters.json
az bicep build-params --file infra/main.proddev.bicepparam --outfile infra/main.proddev.parameters.json
```

## Secure Values Checklist

1. Replace placeholder passwords/secrets before deploy.
2. Never commit real credentials or tenant-specific IDs.
3. Keep production secrets in your secret manager.
4. Confirm `operatorIps` includes your current deploy runner IP.
