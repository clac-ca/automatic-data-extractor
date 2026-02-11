# Authentication API Reference

## Purpose

Document auth/session endpoints and API-key access checks for ADE integrations.

## Authentication Requirements

ADE supports two authentication transports:

- API key header: `X-API-Key: <key>`
- Session cookie: browser session cookie issued by interactive auth flows

For service integrations, use `X-API-Key`.

## Endpoint Matrix

### Auth Endpoints

| Method | Path | Auth | Primary status | Request shape | Response shape | Common errors |
| --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/auth/login` | public | `200` | JSON: email/password | JSON: auth state (`success` or MFA challenge) | `401` invalid credentials |
| `POST` | `/api/v1/auth/logout` | protected | `204` | no body | empty | `401` missing auth, `403` CSRF |
| `POST` | `/api/v1/auth/mfa/challenge/verify` | public | `200` | JSON: challenge token + code | JSON: auth success | `400`, `401` invalid challenge/code |
| `GET` | `/api/v1/auth/mfa/totp` | protected | `200` | none | JSON: MFA status | `401` |
| `DELETE` | `/api/v1/auth/mfa/totp` | protected | `204` | none | empty | `401`, `403` CSRF |
| `POST` | `/api/v1/auth/mfa/totp/enroll/confirm` | protected | `200` | JSON: enrollment code | JSON: recovery codes | `400`, `401`, `403` |
| `POST` | `/api/v1/auth/mfa/totp/enroll/start` | protected | `200` | none | JSON: OTP URI metadata | `401`, `403` |
| `POST` | `/api/v1/auth/mfa/totp/recovery/regenerate` | protected | `200` | JSON: current code | JSON: new recovery codes | `400`, `401`, `403` |
| `POST` | `/api/v1/auth/password/forgot` | public | `202` | JSON: email | empty | `400` invalid payload |
| `POST` | `/api/v1/auth/password/reset` | public | `204` | JSON: reset token + new password | empty | `400` token invalid/expired |
| `POST` | `/api/v1/auth/password/change` | protected | `204` | JSON: current password + new password | empty | `400`, `401`, `403`, `422` |
| `GET` | `/api/v1/auth/providers` | public | `200` | none | JSON: provider list | none typical |
| `GET` | `/api/v1/auth/setup` | public | `200` | none | JSON: setup state | none typical |
| `POST` | `/api/v1/auth/setup` | public | `204` | JSON: first-admin payload | empty + session cookies | `409` setup already completed |
| `GET` | `/api/v1/auth/sso/authorize` | public | `200` | query: `returnTo` optional | redirect or JSON status | `429` throttled, provider errors |
| `GET` | `/api/v1/auth/sso/callback` | public | `200` | query: `code`/`state` | redirect or JSON status | provider validation failures |
| `GET` | `/api/v1/auth/sso/providers` | public | `200` | none | JSON: active SSO providers | none typical |

### Me Endpoints

| Method | Path | Auth | Primary status | Request shape | Response shape | Common errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/me` | protected | `200` | none | JSON: current user profile | `401`, `403` service account |
| `PATCH` | `/api/v1/me` | protected | `200` | JSON: editable profile fields | JSON: updated profile | `401`, `403`, `422` invalid patch |
| `GET` | `/api/v1/me/bootstrap` | protected | `200` | none | JSON: profile + roles + permissions + workspaces | `401`, `403` |
| `GET` | `/api/v1/me/permissions` | protected | `200` | none | JSON: effective permissions | `401` |
| `POST` | `/api/v1/me/permissions/check` | protected | `200` | JSON: permissions to evaluate | JSON: evaluation result | `401`, `404`, `422` |

## Core Endpoint Details

### `POST /api/v1/auth/login`

- Request body: local credentials.
- Response: session success payload or MFA challenge payload.
- Cookies: session and CSRF cookies are set on success.

### `GET /api/v1/me`

- Preferred API-key smoke test endpoint.
- Request: include `X-API-Key`.
- Response: profile fields for the authenticated principal.

### `GET /api/v1/auth/providers`

- Public provider discovery endpoint.
- Useful for login UX decisions before calling interactive auth routes.

### `POST /api/v1/auth/password/change`

- Protected endpoint for authenticated password rotation.
- Requires current password and a new password that satisfies active policy.
- Returns no body on success.

## Error Handling

Auth endpoints can return standard Problem Details responses.

- `401 Unauthorized`: missing, expired, or invalid credentials.
- `403 Forbidden`: principal authenticated but lacks required access or CSRF requirements.
- `409 Conflict`: setup/auth flow state conflict.
- `429 Too Many Requests`: rate limiting for SSO/auth hardening.

See [Errors and Problem Details](errors-and-problem-details.md) for shared error format.

## Related Guides

- [Authenticate with API Key](../../how-to/api-authenticate-with-api-key.md)
