# Security and Authentication

## Purpose

Explain ADE security decisions in plain language: who can access ADE, how ADE authenticates, and how production network access should be restricted.

## Authentication Modes

- Standard auth (recommended for production)
- SSO provider auth
- Auth-disabled mode (`ADE_AUTH_DISABLED=true`) for local development only

## Authorization Model

ADE uses role-based access control:

- **Global role**: permissions across all workspaces
- **Workspace role**: permissions scoped to a single workspace

## Core Security Settings

- `ADE_SECRET_KEY`
- `ADE_PUBLIC_WEB_URL`
- `ADE_AUTH_DISABLED`
- `ADE_AUTH_FORCE_SSO`
- `ADE_SSO_ENCRYPTION_KEY`
- `ADE_BLOB_ACCOUNT_URL` or `ADE_BLOB_CONNECTION_STRING`
- `ADE_DATABASE_AUTH_MODE`

## Production Network Profiles

### Profile A: Public Endpoints + Strict Allowlists (lower cost)

Use when you want strong controls without Private Link cost.

- PostgreSQL uses public access with explicit firewall rules for allowed IPs.
- Storage uses firewall default deny with explicit IP rules and VNet rules.
- ACA subnet uses Storage service endpoints for app-to-storage access.
- Keep broad rules (for example `0.0.0.0`) temporary only.

### Profile B: Private Endpoints + Private DNS (strongest isolation)

Use when policy requires private-only data-plane access.

- PostgreSQL and Storage use private endpoints.
- Private DNS zones are linked to the app VNet.
- Public network access is disabled where supported.

## Devices and VNet Clarification

- Devices are not directly attached to an Azure VNet like Azure resources.
- Use Point-to-Site VPN or ExpressRoute for device/on-prem access to VNet resources.
- Even with service endpoints, on-prem/device flows can still require public NAT IP allowlists for Storage.

## Managed Identity Baseline

- Use system-assigned identity on the ADE container app.
- Prefer `ADE_BLOB_ACCOUNT_URL` + RBAC over storage connection strings.
- Grant `Storage Blob Data Contributor` to the app identity on the blob container scope.
- PostgreSQL managed identity auth is optional and requires Entra admin plus DB role mapping.

## Production Security Checklist

- `ADE_AUTH_DISABLED=false`
- strong random `ADE_SECRET_KEY`
- `ADE_PUBLIC_WEB_URL` matches real HTTPS URL
- one chosen network profile is implemented end-to-end
- managed identity and blob RBAC are configured
- `/app/data` is persisted on Azure Files

## Safe Mode

Set `ADE_SAFE_MODE=true` to disable engine execution during controlled maintenance or incident response.

## Related

- [Production Bootstrap](../tutorials/production-bootstrap.md)
- [Deploy to Production](../how-to/deploy-production.md)
- [Environment Variables](../reference/environment-variables.md)
