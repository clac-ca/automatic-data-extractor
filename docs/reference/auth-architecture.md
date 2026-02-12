# Auth Architecture

One-page reference for ADE authentication, authorization, provisioning policy, and
IdP/SCIM behavior.

## Auth Model

ADE supports two runtime auth channels:

1. browser auth: session cookie + CSRF token
2. machine auth: `X-API-Key`

SCIM provisioning uses dedicated SCIM bearer tokens managed by
`/api/v1/admin/scim/tokens*`.

## Browser Session Flow

1. user signs in via `POST /api/v1/auth/login` or SSO callback flow
2. API sets session and CSRF cookies
3. mutating browser requests must include `X-CSRF-Token`
4. `POST /api/v1/auth/logout` ends session

## MFA and Password Flows

- TOTP enrollment/challenge and recovery code flows are available for password-authenticated sessions.
- Password reset depends on runtime policy and mode.
- Forced-password-change users can only access onboarding-safe routes until password update succeeds.

## Provisioning Policy Model

Provisioning policy is controlled via admin settings:

- `auth.identityProvider.provisioningMode`
  - `disabled`
  - `jit`
  - `scim`

Mode behavior:

1. `disabled`: unknown SSO users are denied until invited/admin-provisioned.
2. `jit`: unknown users can be created/linked at successful SSO sign-in per policy checks.
3. `scim`: unknown SSO users are denied at login; SCIM/invitation paths provide provisioning.

## IdP Group Membership Behavior

1. JIT does not perform any group synchronization.
2. SCIM is the only automatic path for provider-managed group and membership sync.
3. Provider-managed group assignments are effective only when provisioning mode is `scim`.
4. Manual membership mutations are blocked for provider-managed groups.

## SCIM Provisioning Model

1. SCIM endpoints live at `/scim/v2/*`.
2. SCIM routes are active only when provisioning mode is `scim`.
3. SCIM `/Bulk` is not enabled in current scope.
4. Deprovisioning is handled via `active=false` semantics.

## Authorization (RBAC)

Authorization uses principal-aware role assignments:

1. principal types: `user`, `group`
2. scope types: `organization`, `workspace`
3. effective permissions are union of direct and group-derived grants
4. inactive users are denied regardless of assignment state

## Credential Transport Rules

1. API key transport: `X-API-Key` only
2. `Authorization: Bearer` is not an API-key channel

## Non-Production Mode

`ADE_AUTH_DISABLED=true` is local/non-production only and must not be enabled in
production.

## Related

- [Authentication API Reference](api/authentication.md)
- [Access Management API Reference](api/access-management.md)
- [Access Reference](access/README.md)
- [Auth Operations](../how-to/auth-operations.md)
