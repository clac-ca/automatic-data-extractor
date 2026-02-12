# Auth Operations Runbook

## Goal

Operate ADE authentication safely in production using the Authentication Policy V2 model.

## Canonical Routes

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/password/forgot`
- `POST /api/v1/auth/password/reset`
- `POST /api/v1/auth/password/change`
- `POST /api/v1/auth/mfa/challenge/verify`
- `POST /api/v1/admin/sso/providers/validate`
- `GET/POST/PATCH/DELETE /api/v1/admin/sso/providers*`
- `GET/PATCH /api/v1/admin/settings`

Do not use removed legacy auth route namespaces.

## Authentication Policy Model

Runtime policy lives in `auth` under `/api/v1/admin/settings`:

- `auth.mode`: `password_only | idp_only | password_and_idp`
- `auth.password.*`: password-reset, MFA requirement, complexity, lockout
- `auth.identityProvider.jitProvisioningEnabled`

## Setup First, Policy Second

Use this rollout order:

1. Configure provider metadata.
2. Validate provider connection (`POST /api/v1/admin/sso/providers/validate`).
3. Save provider and set provider status.
4. Update `auth.mode` and related policy settings.

Provider setup does not auto-change policy mode.

## Provider Lifecycle

Preferred lifecycle API is `PATCH /api/v1/admin/sso/providers/{id}`:

- set `status=active` to enable provider sign-in
- set `status=disabled` to disable provider sign-in

UI/API status values are user-facing only: `active` and `disabled`.

## Mode Behavior

- `password_only`: password sign-in available; IdP sign-in unavailable.
- `password_and_idp`: both sign-in methods available.
- `idp_only`: organization members use IdP sign-in; global admins still have password + MFA break-glass access.

## Password Reset Behavior

Password reset is available only when:

- `auth.password.resetEnabled=true`
- `auth.mode != idp_only`

Forgot/reset endpoints return `403` when reset is disabled by policy.

## MFA Behavior

- `auth.password.mfaRequired=true` requires MFA enrollment for password-authenticated sessions before protected API access.
- SSO and API-key sessions are not forced by password MFA policy.

## Password Policy Behavior

Password checks use runtime settings:

- `auth.password.complexity.*`
- `auth.password.lockout.*`

These are enforced for:

- first-admin creation
- admin-created/reset passwords
- password reset flow
- failed password login lockout

## User Provisioning Contract

`POST /api/v1/users` now requires `passwordProfile`:

- `mode=explicit`: caller provides `passwordProfile.password`.
- `mode=auto_generate`: API generates a compliant password and returns it one time in `passwordProvisioning.initialPassword`.
- `forceChangeOnNextSignIn`: when `true`, user must change password before normal app access.

No implicit hidden-random-password behavior is supported.

## IdP Group Sync Contract

When IdP group sync is enabled:

- Background sync auto-creates/updates IdP groups and reconciles memberships for known ADE users only.
- Background sync does not create missing ADE users from directory membership snapshots.
- Known-user linking uses existing external mappings first, then SSO subject mapping, then guarded email linking for allowed provider domains.
- First successful SSO sign-in hydrates that user's group memberships so access updates immediately.
- Invitation workflows and JIT provisioning remain the user-creation paths.

## Forced Password Change Behavior

- Login success includes `passwordChangeRequired`.
- Flagged users can access onboarding endpoints
  (`/api/v1/me/bootstrap`, MFA routes, logout, `/api/v1/auth/password/change`)
  and are blocked from other protected routes with
  `403 password_change_required`.
- `POST /api/v1/auth/password/change` clears the requirement after successful change.

## SSO Validation Failure Codes

`POST /api/v1/admin/sso/providers/validate` may return:

- `sso_discovery_failed`
- `sso_issuer_mismatch`
- `sso_metadata_invalid`
- `sso_validation_timeout`

Operational actions:

- `sso_discovery_failed`: verify issuer URL reachability and OIDC metadata endpoint.
- `sso_issuer_mismatch`: ensure configured issuer exactly matches metadata issuer.
- `sso_metadata_invalid`: provider metadata is incomplete/invalid.
- `sso_validation_timeout`: verify DNS/TLS/network egress from ADE to issuer.

## API Key Contract

- API keys are accepted only via `X-API-Key`.
- `Authorization: Bearer` is not an API-key transport channel.

## Observability Checklist

Track and alert on:

- repeated password login failures and lockout spikes
- MFA challenge failures and recovery code spikes
- password reset request spikes/failures
- SSO callback/provider validation failures
- admin settings update failures

## Validation Commands

```bash
cd backend && uv run ade api test
cd backend && uv run ade test
cd backend && uv run ade api types
```

## Post-Change Smoke Checklist

1. Password login/logout works as expected for selected `auth.mode`.
2. SSO sign-in works for active providers.
3. Global-admin break-glass password path still works in `idp_only` mode.
4. Forgot/reset behavior matches policy.
5. Admin settings and provider lifecycle updates succeed.
