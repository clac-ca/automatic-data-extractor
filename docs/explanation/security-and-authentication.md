# Security and Authentication

## Purpose

Explain ADE security decisions in plain language: who can access ADE, how ADE authenticates, and how production network access should be restricted.

## Authentication Modes

- Built-in ADE auth (recommended for production)
- Optional external SSO provider auth (OIDC)
- Auth-disabled mode (`ADE_AUTH_DISABLED=true`) for local development only

### Runtime Credential Channels

- Browser session cookie (`SessionCookie`) + CSRF token.
- API key header (`X-API-Key`) for programmatic access.
- Legacy JWT/cookie auth route namespaces are not part of the active runtime contract.

## Authorization Model

ADE uses role-based access control:

- **Global role**: permissions across all workspaces
- **Workspace role**: permissions scoped to a single workspace

Runtime authorization is role/permission driven. Do not rely on legacy `is_superuser` bypass assumptions.

## SSO Enforcement Model

- SSO enforcement is managed via `GET/PUT /api/v1/admin/sso/settings`.
- When `enforceSso=true`, non-global-admin local login is blocked.
- Global-admin local login remains available for emergency operational access and requires MFA enrollment.

## Local MFA Enforcement Model

- `ADE_AUTH_ENFORCE_LOCAL_MFA=true` enforces MFA onboarding for password-authenticated sessions.
- When enabled, users signed in with built-in auth must complete TOTP enrollment before most protected endpoints are accessible.
- SSO and API key sessions are not forced by this setting.

## Core Security Settings

- `ADE_SECRET_KEY`
- `ADE_PUBLIC_WEB_URL`
- `ADE_AUTH_DISABLED`
- `ADE_AUTH_FORCE_SSO`
- `ADE_AUTH_PASSWORD_RESET_ENABLED`
- `ADE_AUTH_ENFORCE_LOCAL_MFA`
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
- `X-API-Key` is the only API-key transport accepted by clients
- one chosen network profile is implemented end-to-end
- managed identity and blob RBAC are configured
- `/app/data` is persisted on Azure Files

## Safe Mode

Set `ADE_SAFE_MODE=true` to disable engine execution during controlled maintenance or incident response.

## Related

- [Auth Architecture](../reference/auth-architecture.md)
- [Auth Operations Runbook](../how-to/auth-operations.md)
- [Production Bootstrap](../tutorials/production-bootstrap.md)
- [Deploy to Production](../how-to/deploy-production.md)
- [Environment Variables](../reference/environment-variables.md)
