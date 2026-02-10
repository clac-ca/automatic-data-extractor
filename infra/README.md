# ADE Azure Infra (Bicep)

This is the only Azure infrastructure deployment surface for ADE.

## Files

- `infra/main.bicep`: single source of truth
- `infra/main.prod.bicepparam`: prod-only scenario
- `infra/main.proddev.bicepparam`: prod+dev scenario
- `infra/main.json`: generated ARM template for Azure Portal
- `infra/main.prod.parameters.json`: generated prod portal parameters
- `infra/main.proddev.parameters.json`: generated prod+dev portal parameters

## Scenario Choice

- **Prod only**: deploy shared infra + prod app
- **Prod + Dev**: deploy shared infra + prod app + dev app

The only change between scenarios is which `.bicepparam` file you deploy.

## CLI Deploy (recommended)

```bash
az login
az account set --subscription "<SUBSCRIPTION_ID>"

az group create \
  --name rg-ade-shared-canadacentral-001 \
  --location canadacentral
```

Edit placeholders in one scenario file:

- `infra/main.prod.bicepparam` or
- `infra/main.proddev.bicepparam`

Set real values for:

- `postgresAdminPassword`
- `postgresEntraAdminObjectId`
- `postgresEntraAdminPrincipalName`
- `prodImage`, `prodWebUrl`, `prodSecretKey`
- `devImage`, `devWebUrl`, `devSecretKey` (prod+dev only)
- `operatorIps`

Preview:

```bash
az deployment group what-if \
  --resource-group rg-ade-shared-canadacentral-001 \
  --name ade-prod-whatif \
  --parameters infra/main.prod.bicepparam
```

Deploy prod:

```bash
az deployment group create \
  --resource-group rg-ade-shared-canadacentral-001 \
  --name ade-prod \
  --parameters infra/main.prod.bicepparam
```

Deploy prod+dev:

```bash
az deployment group create \
  --resource-group rg-ade-shared-canadacentral-001 \
  --name ade-proddev \
  --parameters infra/main.proddev.bicepparam
```

## Portal Deploy

Use ARM JSON artifacts generated from the same Bicep source.

Deploy button:

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fclac-ca%2Fautomatic-data-extractor%2Fmain%2Finfra%2Fmain.json)

In portal:

1. Select subscription and resource group.
2. Upload `infra/main.prod.parameters.json` or `infra/main.proddev.parameters.json`.
3. Replace placeholder secure values.
4. Start deployment.

## Managed Identity Database Grant (manual)

Blob RBAC is done in Bicep. PostgreSQL in-database role mapping is a manual SQL step when `databaseAuthMode=managed_identity` (default).

```bash
RG=rg-ade-shared-canadacentral-001
DEPLOYMENT=ade-prod

POSTGRES_FQDN=$(az deployment group show --resource-group "$RG" --name "$DEPLOYMENT" --query properties.outputs.postgresFqdn.value -o tsv)
POSTGRES_PROD_DB=$(az deployment group show --resource-group "$RG" --name "$DEPLOYMENT" --query properties.outputs.postgresProdDb.value -o tsv)
PROD_APP_NAME=$(az deployment group show --resource-group "$RG" --name "$DEPLOYMENT" --query properties.outputs.prodAppName.value -o tsv)
PROD_APP_OID=$(az deployment group show --resource-group "$RG" --name "$DEPLOYMENT" --query properties.outputs.prodAppPrincipalId.value -o tsv)
PG_ADMIN_UPN=<postgres_entra_admin_principal_name>
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

For `prod+dev`, repeat for `devAppName`, `devAppPrincipalId`, and `postgresDevDb` outputs.

## Regenerate Portal Artifacts

Run after editing `infra/main.bicep` or either `.bicepparam` file:

```bash
az bicep build --file infra/main.bicep --outfile infra/main.json
az bicep build-params --file infra/main.prod.bicepparam --outfile infra/main.prod.parameters.json
az bicep build-params --file infra/main.proddev.bicepparam --outfile infra/main.proddev.parameters.json
```

## Teardown

```bash
az group delete --name rg-ade-shared-canadacentral-001 --yes --no-wait
```
