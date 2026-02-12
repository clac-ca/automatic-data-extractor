# Access Management Incident Runbook

## Symptom

Access behavior is incorrect (unexpected allow/deny, missing membership, failed
invite provisioning, SCIM failures, or broken workspace delegation).

## Diagnosis

### Immediate triage

1. Identify scope: organization or workspace.
2. Identify principal type: user or group.
3. Check user activity state (`is_active`).
4. Confirm direct assignments and group-derived assignments.
5. Confirm provisioning mode (`disabled|jit|scim`).
6. Confirm whether operation path was interactive API, batch API, or SCIM.

### Fast checks

```bash
cd backend && uv run ade api test
cd backend && uv run ade api types
```

## Action

### Incorrect deny for expected access

1. Verify assignment exists at correct scope.
2. Verify group membership is present for inherited grants.
3. Verify role contains required permission key.
4. For JIT mode, verify sign-in hydration completed for affected user.

### Unexpected allow

1. Check inherited group grants and workspace assignments.
2. Remove incorrect assignment(s).
3. Re-test using `me/permissions` and targeted endpoint call.

### Invitation failures

1. Validate inviter permissions in target scope.
2. Validate role assignment payload and scope IDs.
3. Recreate invitation when state is cancelled/expired.

### SCIM failures

1. Validate provisioning mode is `scim`.
2. Validate SCIM token status and last used metadata.
3. Verify SCIM request and response envelopes in logs.

## Verify

1. Affected principal has expected effective permissions.
2. Unauthorized principals are denied consistently.
3. Invitation or SCIM retry path succeeds.
4. No elevated error rates in access endpoints.

## Escalation

Escalate when:

1. permission boundary appears bypassed
2. repeated SCIM or invitation failures persist after token/config fixes
3. production impact spans multiple workspaces or tenants

## Related

- [Access Reference](../reference/access/README.md)
- [Auth Incident Runbook](auth-incident-runbook.md)
- [Auth Operations](../how-to/auth-operations.md)
