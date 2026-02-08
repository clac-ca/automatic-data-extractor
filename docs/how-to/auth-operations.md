# Auth Operations Runbook

## Goal

Operate ADE auth safely in production with one consistent control path.

## Canonical Routes

Use only:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/password/forgot`
- `POST /api/v1/auth/password/reset`
- `POST /api/v1/auth/mfa/challenge/verify`
- `GET/PUT /api/v1/admin/sso/settings`

Do not use legacy JWT or cookie route namespaces.

## SSO Enforcement Operations

1. Ensure at least one active external provider exists (`/api/v1/admin/sso/providers*`).
2. Set settings via `PUT /api/v1/admin/sso/settings`:
- `enabled`
- `enforceSso`
- `allowJitProvisioning`
3. Validate behavior:
- regular local user login is blocked (`sso_enforced`)
- global-admin local login remains available
- global-admin local login still requires MFA enrollment

## Global-Admin Local Login Exception

When SSO is enforced:

- global-admin users can still use local login for emergency admin access.
- global-admin users must keep MFA enabled for local login.

## Password Reset Operations

- Forgot endpoint is intentionally uniform (`202`) for known and unknown emails.
- If `ADE_AUTH_PASSWORD_RESET_ENABLED=false` or SSO enforcement is enabled, forgot/reset endpoints return `403`.
- Reset tokens are one-time and time-limited.
- Delivery adapter may be no-op until SMTP integration is configured.

## MFA Recovery Code Behavior

- Accept `XXXX-XXXX` and `XXXXXXXX` input styles.
- Recovery codes are single-use.
- Failed/replayed code attempts should not grant session creation.

## API Key Transport Contract

- Programmatic auth must use `X-API-Key`.
- Bearer headers are not valid API key transport.

## Observability and Alerts

Track and alert on:

- repeated login failures and lockout events
- MFA challenge failures and recovery-code usage spikes
- password reset request spikes and reset failures
- API key auth failures and denied access bursts
- SSO callback/provider failures and policy update failures

Create alerts for sustained error-rate or anomaly spikes, not single-request failures.

## Secret Management and Rotation

Auth-related secrets to manage and rotate:

- `ADE_SECRET_KEY`
- `ADE_SSO_ENCRYPTION_KEY` (when set)
- external IdP client secrets

After rotation, run the post-change smoke checklist and confirm login, MFA, reset, and SSO provider operations still work.

## Security Validation Commands

```bash
cd backend && uv run ade api test
cd backend && uv run ade test
cd backend && uv run python -m ade_api.scripts.generate_openapi
cd backend && uv run ade api types
```

## Post-Change Smoke Checklist

1. Local login/logout (with CSRF on logout).
2. MFA challenge and recovery code success/replay behavior.
3. Forgot/reset flows.
4. SSO settings read/write.
5. API key auth via `X-API-Key`.
