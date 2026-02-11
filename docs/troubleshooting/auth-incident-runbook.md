# Auth Incident Runbook

## Symptom

Use this runbook when any of these conditions are true:

- account lockout spikes
- SSO authorization or callback failures
- global-admin access loss
- suspected token abuse

## Diagnosis

### Immediate Triage

1. Confirm impact scope.

   - all users or subset
   - password auth, SSO, or API key

1. Confirm recent changes.

   - deploys
   - config updates
   - secret rotations

1. Validate health and logs.

   - auth failures
   - CSRF failures
   - SSO callback/provider failures
   - API key auth failures

## Action

### Account Lockout Recovery

1. Identify affected users.
1. Check failed-login counters and lockout windows.
1. Restore access using approved admin controls.
1. Require password reset and MFA verification when suspicious activity exists.

### SSO Outage Fallback

1. Confirm provider outage or misconfiguration.
1. If `auth.mode=idp_only` blocks member access, use global-admin break-glass
   password + MFA login.
1. Keep global-admin MFA enabled.
1. Move to `password_and_idp` only with incident-lead approval.

### Admin Access Recovery

1. Regain access with a global-admin account protected by MFA.
1. Validate `/api/v1/admin/settings` and provider status.
1. Re-apply expected auth policy fields:
   `auth.mode`, `auth.password.*`,
   `auth.identityProvider.jitProvisioningEnabled`.

## Verify

After remediation, confirm:

1. local login works
1. session creation and validation work
1. provider secret decrypt/encrypt flows work
1. password reset and MFA flows pass

## Escalation

Escalate immediately if:

- access cannot be restored with break-glass procedure
- suspicious auth activity continues after remediation
- policy state cannot be reconciled with expected production settings
