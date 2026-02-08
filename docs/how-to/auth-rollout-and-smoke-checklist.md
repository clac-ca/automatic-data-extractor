# Auth Rollout and Smoke Checklist

## Rollout Sequence

1. Development
2. Staging
3. Production

## Pre-Deploy Gate

1. `cd backend && uv run ade api test`
2. `cd backend && uv run ade test`
3. `cd backend && uv run python -m ade_api.scripts.generate_openapi`
4. `cd backend && uv run ade api types`
5. Confirm no generated artifact drift:

```bash
git diff -- backend/src/ade_api/openapi.json frontend/src/types/generated/openapi.d.ts
```

## Deploy Steps per Environment

1. Deploy application artifacts.
2. Verify auth environment variables and secrets.
3. Run smoke tests below.

## Smoke Tests

1. Local login success.
2. Logout requires CSRF and succeeds with CSRF.
3. MFA enrollment + challenge verify works.
4. Recovery code works once and replay fails.
5. Forgot-password returns uniform `202`.
6. Password reset token is single-use.
7. SSO enforcement blocks non-admin local login.
8. Global-admin local login remains available with MFA.
9. API key auth works via `X-API-Key` and rejects bearer style.
10. RBAC-protected endpoint behavior is unchanged.

## 48-Hour Post-Release Review

Collect and review:

- login failure rate
- lockout events
- MFA failure/recovery usage
- password reset request volume and reset completion rate
- API key auth failure rate
- SSO callback/auth failures

Open only targeted remediation tickets for regressions or security findings.
