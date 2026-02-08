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
- Reset tokens are stored as hashes, not plaintext.
- Admin toggle: `ADE_AUTH_PASSWORD_RESET_ENABLED=false` disables forgot/reset endpoints and public UI.
- SSO interaction: when `enforceSso=true`, password reset endpoints are unavailable in public flows.

## SSO and Enforcement

- Admin policy surface: `GET/PUT /api/v1/admin/sso/settings`.
- External provider management: `/api/v1/admin/sso/providers*`.
- SSO enforcement behavior:
- non-global-admin local login is blocked when `enforceSso=true`
- global-admin local login remains allowed but must satisfy MFA requirement

## Authorization (RBAC)

- Authorization is role/permission based.
- No `is_superuser` bypass path is used in runtime permission evaluation.

## Credential Transport Rules

- API keys: `X-API-Key` only.
- `Authorization: Bearer ...` is not an API key channel.

## Non-Production Mode

- `ADE_AUTH_DISABLED=true` is for local/non-production only.
- Auth-disabled mode should remain deterministic and isolated from production configs.
