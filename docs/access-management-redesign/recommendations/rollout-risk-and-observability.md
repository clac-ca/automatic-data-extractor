# Rollout Risk and Observability

## Cutover Strategy

Hard cutover in one coordinated release (backend + frontend + migrations).

1. Deploy additive schema and backfill job.
2. Deploy backend with normalized routes and provisioning-mode behavior.
3. Deploy frontend route/IA cutover.
4. Run post-deploy verification suite and observability checks.

## Primary Risks and Mitigations

### Risk 1: Permission regressions at scope boundaries

- Mitigation:
  - permission matrix test suite (org vs workspace)
  - pre/post comparison for known admin personas
  - deny-by-default for unknown permission keys

### Risk 2: Duplicate identity creation during invite/JIT/SCIM interactions

- Mitigation:
  - canonical email uniqueness
  - external-id uniqueness constraints
  - transaction-level upsert behavior
  - conflict telemetry on duplicate attempts

### Risk 3: Assignment migration errors

- Mitigation:
  - row-count parity checks between legacy and new assignment tables
  - sample-based diff of effective permissions per user/workspace

### Risk 4: Provisioning mode drift or misconfiguration

- Mitigation:
  - explicit mode audit events on change
  - startup validation for mode/config combinations
  - dashboard gauge for current provisioning mode

### Risk 5: JIT membership hydration failures during login

- Mitigation:
  - do not block login on transient hydration failure
  - queue async retry
  - alert on hydration failure rate

### Risk 6: SCIM contract incompatibility with IdPs

- Mitigation:
  - conformance tests for Entra and Okta flows
  - strict SCIM error schema validation
  - staged pre-prod connector certification

### Risk 7: UI route breakage from hard cutover

- Mitigation:
  - e2e route smoke tests for all new access paths
  - explicit navigation tests on desktop and mobile

### Risk 8: Bulk mutation misuse or partial-failure confusion

- Mitigation:
  - strict subrequest allowlist for `POST /api/v1/$batch`
  - clear per-item statuses in UI and API docs
  - chunking guidance (max 20) and retry-failed-only guidance

## Observability Spec

## Structured Audit Events

Emit events for:

1. `invitation.created`
2. `invitation.resent`
3. `invitation.cancelled`
4. `role_assignment.created`
5. `role_assignment.deleted`
6. `group.created|updated|deleted`
7. `group.membership.added|removed`
8. `auth.provisioning_mode.changed`
9. `auth.jit.user_provisioned`
10. `auth.jit.membership_hydration.completed|failed`
11. `scim.request.received|completed|failed`
12. `users.batch.request.received|completed|failed`
13. `users.batch.item.completed|failed`

Required fields:

- `actor_user_id` (if interactive)
- `channel` (`invite|jit|scim|admin`)
- `principal_type`, `principal_id`
- `scope_type`, `scope_id`
- `role_id`
- `correlation_id`
- `timestamp`

## Metrics

1. Invitation funnel:
   - invites created
   - accepts
   - expiry/cancel counts
2. Access mutations:
   - assignments created/deleted
   - group membership mutations
3. JIT health:
   - hydration success/fail
   - hydration latency
4. SCIM health:
   - request volume by endpoint/method
   - success/failure rates
   - latency percentiles
5. Authz failures:
  - permission denied by endpoint + permission key
6. Bulk endpoint health:
  - batch envelope count
  - items per batch distribution
  - item failure ratio by status code
  - dependency-failure (`424`) counts

## Alerts

1. Spike in permission-denied rates after deployment.
2. Invitation conflict/duplicate spikes.
3. JIT hydration failure rate above threshold.
4. SCIM 4xx/5xx rates above threshold.
5. Access-evaluator errors > SLO.
6. Bulk endpoint item failure ratio above threshold.

## Acceptance Scenarios (Release Gates)

1. Workspace owner invites unknown email and assigns workspace role without org user permission.
2. Workspace owner adds existing user by email; no duplicate user record is created.
3. Group grant in workspace produces effective permissions for all relevant group members.
4. Direct user role + group role union is deterministic and correct.
5. Deactivating a user removes effective access even with group grants.
6. In JIT mode, sign-in hydrates group membership for that user without creating unrelated users.
7. In SCIM mode, SCIM user/group updates apply without JIT fallback creation.
8. Workspace owner cannot edit organization users/roles globally.
9. Mobile and desktop flows are equivalent for core add/manage actions.
10. Bulk user create/update/deactivate batch flows pass with mixed outcomes and clear operator feedback.

## Exit Criteria

1. All acceptance scenarios pass.
2. No unresolved P0/P1 permission defects.
3. JIT/SCIM telemetry healthy for defined soak window.
