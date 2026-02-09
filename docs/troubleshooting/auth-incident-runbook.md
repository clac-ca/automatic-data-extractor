# Auth Incident Runbook

## Scope

Use this runbook for auth-related production incidents:

- account lockout spikes
- SSO outage or callback failures
- admin access loss
- auth token abuse signals

## Immediate Triage

1. Confirm impact scope:
- all users vs subset
- local auth vs SSO vs API key
2. Confirm recent changes:
- deploy, config, secret rotation
3. Validate health and logs:
- auth failures
- CSRF failures
- SSO callback/provider errors
- API key auth failures

## Account Lockout Recovery

1. Identify affected user(s).
2. Verify failed-login counters and lock window.
3. Use admin tooling to restore access as appropriate.
4. Require password reset and MFA verification if suspicious activity exists.

## SSO Outage Fallback

1. Confirm provider outage/misconfiguration.
2. If `auth.mode=idp_only` and member access is blocked, use global-admin password + MFA break-glass login.
3. Ensure global-admin MFA remains enabled.
4. Temporarily change mode to `password_and_idp` only if required for continuity and approved by incident lead.

## Admin Access Recovery

1. Use a global-admin account with MFA to regain control.
2. Validate `/api/v1/admin/settings` and provider status.
3. Re-establish expected policy (`auth.mode`, `auth.password.*`, `auth.identityProvider.jitProvisioningEnabled`).

## Secret Rotation Verification

After rotating auth-related secrets:

1. Verify local login works.
2. Verify session creation/validation works.
3. Verify provider secret decrypt/encrypt flows still work.
4. Verify password reset and MFA flows still pass.

## Incident Closeout

1. Document root cause and timeline.
2. Record user impact and duration.
3. Add remediation action items with owners.
4. Update auth docs/tests if behavior changed.
