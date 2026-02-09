# Triage Playbook

## Goal

Move from symptom to confirmed cause quickly, with the fewest checks possible.

## First 5 Minutes

1. Confirm blast radius:
   - one user
   - one workspace
   - all users
2. Confirm deployment model:
   - Azure Container Apps production
   - local Docker Compose dev
3. Check health endpoints:

```bash
curl -sS <web-url>/api/v1/health
curl -sS <web-url>/api/v1/info
```

4. Pull recent app logs:

```bash
az containerapp logs show --name ade-app --resource-group <resource-group> --tail 200
```

## Branch by Symptom

### Web App Is Down

Check:

- app running status
- latest revision status
- ingress/FQDN settings

```bash
az containerapp show --name ade-app --resource-group <resource-group> --query properties.runningStatus -o tsv
az containerapp revision list --name ade-app --resource-group <resource-group> -o table
```

### Login/Auth Fails

Check:

- `ADE_PUBLIC_WEB_URL` matches external URL
- `ADE_AUTH_DISABLED` is false in production
- SSO provider settings if enabled

### Database Errors

Check:

- `ADE_DATABASE_URL` is valid
- PostgreSQL firewall rules include required sources
- app outbound IPs still match firewall allowlist
- migration state if schema errors appear

```bash
az postgres flexible-server firewall-rule list --resource-group <rg> --name <pg-server> --output table
az containerapp show --name ade-app --resource-group <rg> --query properties.outboundIpAddresses -o tsv
```

### Storage Errors

Check:

- exactly one blob auth method is configured
- app identity has blob RBAC when using `ADE_BLOB_ACCOUNT_URL`
- storage firewall default is `Deny` with explicit IP/VNet rules
- service endpoint on ACA subnet exists (Profile A)
- private endpoint + private DNS are healthy (Profile B)

```bash
az storage account network-rule list --resource-group <rg> --account-name <storage-account> -o json
```

### Runs Stuck or Slow

Check:

- app and worker paths are healthy
- `ADE_WORKER_RUN_CONCURRENCY`
- replica settings
- run lifecycle and retries in [Runtime Lifecycle](../reference/runtime-lifecycle.md)

## What to Capture Before Escalation

- image tag and revision name
- first observed failure time
- affected run IDs/workspace IDs
- relevant logs and command outputs
- redacted env values and changed network rules
