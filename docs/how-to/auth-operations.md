# Auth Operations Runbook

## Goal

Operate ADE authentication and identity provisioning safely in production.

## Canonical Routes

Authentication and admin settings:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/password/forgot`
- `POST /api/v1/auth/password/reset`
- `POST /api/v1/auth/password/change`
- `POST /api/v1/auth/mfa/challenge/verify`
- `GET/PATCH /api/v1/admin/settings`
- `GET/POST/PATCH/DELETE /api/v1/admin/sso/providers*`

SCIM and provisioning:

- `GET/POST /api/v1/admin/scim/tokens`
- `POST /api/v1/admin/scim/tokens/{tokenId}/revoke`
- `/scim/v2/*`

## Authentication Policy Model

Runtime auth policy is managed under `/api/v1/admin/settings`:

- `auth.mode`: `password_only | idp_only | password_and_idp`
- `auth.password.*`: reset, MFA, complexity, lockout
- `auth.identityProvider.provisioningMode`: `disabled | jit | scim`

## Setup Order

Use this sequence:

1. configure and validate IdP provider metadata
2. set provider status (`active`/`disabled`)
3. set auth mode and password policy
4. set provisioning mode
5. if using SCIM, issue SCIM token and validate SCIM endpoint behavior

## Provisioning Mode Behavior

### `disabled`

1. unknown SSO users are denied
2. provisioning paths are invitation and admin create

### `jit`

1. unknown users can be created/linked at successful sign-in (policy dependent)
2. no group synchronization is performed

### `scim`

1. unknown SSO users are denied auto-provisioning at login
2. SCIM is the recommended path for automated user provisioning and group sync

## IdP Group Membership Contract

1. JIT does not create/update/remove provider-managed groups or memberships
2. SCIM is the only automatic path that manages provider-managed groups/memberships
3. provider-managed groups are read-only in manual membership endpoints

## Password and MFA Behavior

1. password reset requires reset enabled and compatible auth mode
2. MFA requirement applies to password-authenticated sessions
3. forced password-change users are limited to onboarding-safe routes until password change succeeds

## SCIM Operations

1. rotate SCIM tokens regularly
2. monitor token usage and revoke unused credentials
3. verify provisioning mode is `scim` before troubleshooting SCIM route errors

## Observability Checklist

Monitor:

1. login and MFA failure spikes
2. password reset failure rates
3. SSO callback failures
4. provisioning-mode change events
5. SCIM token lifecycle events and SCIM error rates
6. invitation and assignment mutation failures

## Validation Commands

```bash
cd backend && uv run ade api test
cd backend && uv run ade test
cd backend && uv run ade api types
```

## Post-Change Smoke Checklist

1. selected auth mode works for expected users
2. break-glass path works for global admins
3. provisioning mode behavior matches policy (`disabled|jit|scim`)
4. workspace-owner invitation flow remains functional
5. SCIM mode gate and SCIM token auth behavior are correct

## Related

- [Authentication API Reference](../reference/api/authentication.md)
- [Access Management API Reference](../reference/api/access-management.md)
- [Access Reference](../reference/access/README.md)
- [Auth Incident Runbook](../troubleshooting/auth-incident-runbook.md)
