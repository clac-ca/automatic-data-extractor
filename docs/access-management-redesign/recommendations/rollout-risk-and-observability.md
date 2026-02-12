# Rollout Risk and Observability

## Cutover Strategy

Hard cutover in one coordinated release (backend + frontend + migrations).

1. Deploy additive schema and backfill job.
2. Deploy backend with new route family and assignment evaluator.
3. Deploy frontend route/IA cutover.
4. Run post-deploy verification suite and observability checks.

## Primary Risks and Mitigations

### Risk 1: Permission regressions at scope boundaries

- Mitigation:
  - permission matrix test suite (org vs workspace)
  - pre/post comparison for known admin personas
  - deny-by-default for unknown permission keys

### Risk 2: Duplicate identity creation during invite flow

- Mitigation:
  - canonical email uniqueness
  - transaction-level upsert behavior for invitation create
  - conflict telemetry on duplicate attempts

### Risk 3: Assignment migration errors

- Mitigation:
  - row-count parity checks between legacy and new assignment tables
  - sample-based diff of effective permissions per user/workspace

### Risk 4: Group sync drift

- Mitigation:
  - sync watermark + run status tracking
  - add/remove counts per sync run
  - alert on stale sync age threshold

### Risk 5: UI route breakage from hard cutover

- Mitigation:
  - e2e route smoke tests for all new access paths
  - explicit navigation tests on desktop and mobile

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
8. `group.sync.run.started|completed|failed`

Required fields:

- `actor_user_id`
- `principal_type`, `principal_id`
- `scope_type`, `scope_id`
- `role_id`
- `source` (`internal|idp_sync`)
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
3. Sync health:
   - run success/fail
   - duration
   - objects processed
   - stale watermark age
4. Authz failures:
   - permission denied by endpoint + permission key

## Alerts

1. Sync failure rate above threshold.
2. Spike in permission-denied rates after deployment.
3. Invitation conflict/duplicate spikes.
4. Access-evaluator errors > SLO.

## Acceptance Scenarios (Release Gates)

1. Workspace owner invites unknown email and assigns workspace role without org user permission.
2. Workspace owner adds existing user by email; no duplicate user record is created.
3. Group grant in workspace produces effective permissions for all group members.
4. Direct user role + group role union is deterministic and correct.
5. Deactivating a user removes effective access even with group grants.
6. Dynamic group sync add/remove updates effective workspace permissions.
7. Workspace owner cannot edit organization users/roles globally.
8. Mobile and desktop flows are equivalent for core add/manage actions.

## Exit Criteria

1. All acceptance scenarios pass.
2. No unresolved P0/P1 permission defects.
3. Sync and invitation metrics healthy for defined soak window.

