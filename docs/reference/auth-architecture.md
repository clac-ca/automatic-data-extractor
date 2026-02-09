# Auth Architecture

This page is the one-page reference for ADE authentication and authorization behavior.

## Auth Model

ADE uses two runtime auth mechanisms:

- Browser auth: cookie-backed session + CSRF token.
- Machine auth: API key in `X-API-Key` header.

JWT bearer login is not part of the active auth model.

## Browser Session Flow

1. User submits credentials to `POST /api/v1/auth/login`.
2. On success, API sets:
   - session cookie (`HttpOnly`, scoped by session settings)
   - CSRF cookie for mutating requests
3. Client includes `X-CSRF-Token` for mutating cookie-authenticated operations.
4. `POST /api/v1/auth/logout` revokes active sessions and clears auth cookies.

## MFA (TOTP + Recovery)

- TOTP enrollment:
  - `POST /api/v1/auth/mfa/totp/enroll/start`
  - `POST /api/v1/auth/mfa/totp/enroll/confirm`
- Challenge completion:
  - `POST /api/v1/auth/mfa/challenge/verify`
- Recovery codes:
  - accepted in both `XXXX-XXXX` and `XXXXXXXX` format
  - single-use semantics enforced server-side

## Password Reset

- Forgot flow: when enabled, `POST /api/v1/auth/password/forgot` returns uniform `202` for known/unknown emails.
- Reset flow: `POST /api/v1/auth/password/reset` consumes one-time token.
- Authenticated change flow: `POST /api/v1/auth/password/change`.
- Reset tokens are stored as hashes, not plaintext.
- Reset is available only when both are true:
  - `auth.password.resetEnabled=true`
  - `auth.mode != idp_only`

## User Provisioning

`POST /api/v1/users` requires an explicit password provisioning profile:

- `passwordProfile.mode=explicit`: caller sends password.
- `passwordProfile.mode=auto_generate`: API returns a one-time generated password.
- `passwordProfile.forceChangeOnNextSignIn=true`: user is gated until password change.

## Forced Password Change Gate

- Login responses include `passwordChangeRequired`.
- When `users.must_change_password=true`, protected routes return `403 password_change_required`.
- Allowed routes during this state include:
  - `/api/v1/me/bootstrap`
  - `/api/v1/auth/password/change`
  - `/api/v1/auth/logout`
  - MFA enrollment/challenge endpoints

## Authentication Modes and SSO

- Admin policy surface: `GET/PATCH /api/v1/admin/settings`.
- External provider management: `/api/v1/admin/sso/providers*`.
- Runtime settings precedence: env override, then DB value, then code default.
- Sign-in policy is mode-driven:
  - `password_only`: password sign-in only
  - `password_and_idp`: both password and IdP sign-in
  - `idp_only`: members use IdP sign-in; global admins retain password + MFA break-glass access
- IdP JIT provisioning is controlled by `auth.identityProvider.jitProvisioningEnabled`.

## Authorization (RBAC)

- Authorization is role/permission based.
- No `is_superuser` bypass path is used in runtime permission evaluation.

## Credential Transport Rules

- API keys: `X-API-Key` only.
- `Authorization: Bearer ...` is not an API key channel.

## Non-Production Mode

- `ADE_AUTH_DISABLED=true` is for local/non-production only.
- Auth-disabled mode should remain deterministic and isolated from production configs.
