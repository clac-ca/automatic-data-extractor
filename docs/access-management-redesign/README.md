# Access Management Redesign (Hard Cutover)

Date: February 12, 2026

This package contains historical research, analysis, and recommendations that drove
ADE access-model and access-UI redesign decisions.

Canonical operational documentation lives in:

1. [Access Management Model](../explanation/access-management-model.md)
2. [Access Reference](../reference/access/README.md)
3. [Access Management API Reference](../reference/api/access-management.md)
4. [Manage Users and Access](../how-to/manage-users-and-access.md)
5. [Auth Operations](../how-to/auth-operations.md)
6. [Access Management Redesign Archive Index](../audits/access-management-redesign-2026Q1.md)

## Scope and Constraints

1. Hard cutover release (no `/v2` API family).
2. Preserve the three outcomes:
   - user outcome: simple and predictable access flows.
   - admin outcome: consistent and auditable controls.
   - developer outcome: normalized, maintainable boundaries.
3. Keep UI clean and task-oriented.
4. Provisioning behavior must remain explicit: `disabled | jit | scim`.

## Decision Summary

1. Principal-aware RBAC (`user` and `group`) across org/workspace scopes.
2. Invitation path remains explicit.
3. Provisioning mode selection remains first-class.
4. Access UI now prioritizes first-class membership management and action affordance
   clarity based on benchmark research.

## Package Index

### Research

1. [`research/codebase-current-state.md`](./research/codebase-current-state.md)
2. [`research/ui-playwright-audit.md`](./research/ui-playwright-audit.md)
3. [`research/industry-patterns.md`](./research/industry-patterns.md)
4. [`research/graph-entra-scim-standards.md`](./research/graph-entra-scim-standards.md)
5. [`research/scim-vendor-patterns.md`](./research/scim-vendor-patterns.md)
6. [`research/provisioning-mode-patterns.md`](./research/provisioning-mode-patterns.md)
7. [`research/graph-entra-bulk-user-patterns.md`](./research/graph-entra-bulk-user-patterns.md)
8. [`research/entra-admin-ui-patterns.md`](./research/entra-admin-ui-patterns.md)
9. [`research/access-ui-task-flows-entra-plus-peers.md`](./research/access-ui-task-flows-entra-plus-peers.md)
10. [`research/access-ui-competitive-patterns-matrix.md`](./research/access-ui-competitive-patterns-matrix.md)

### Analysis

1. [`analysis/problem-statement.md`](./analysis/problem-statement.md)
2. [`analysis/option-matrix.md`](./analysis/option-matrix.md)
3. [`analysis/workspace-owner-user-creation-options.md`](./analysis/workspace-owner-user-creation-options.md)
4. [`analysis/group-membership-models.md`](./analysis/group-membership-models.md)
5. [`analysis/rbac-composition-models.md`](./analysis/rbac-composition-models.md)
6. [`analysis/provisioning-mode-option-matrix.md`](./analysis/provisioning-mode-option-matrix.md)
7. [`analysis/jit-sign-in-membership-only-impact.md`](./analysis/jit-sign-in-membership-only-impact.md)
8. [`analysis/bulk-user-endpoint-option-matrix.md`](./analysis/bulk-user-endpoint-option-matrix.md)
9. [`analysis/batch-route-expansion-candidates.md`](./analysis/batch-route-expansion-candidates.md)
10. [`analysis/frontend-access-ui-gap-analysis.md`](./analysis/frontend-access-ui-gap-analysis.md)
11. [`analysis/group-membership-ux-models.md`](./analysis/group-membership-ux-models.md)
12. [`analysis/action-affordance-and-disabled-state-model.md`](./analysis/action-affordance-and-disabled-state-model.md)

### Recommendations

1. [`recommendations/target-model.md`](./recommendations/target-model.md)
2. [`recommendations/api-routes-hard-cutover.md`](./recommendations/api-routes-hard-cutover.md)
3. [`recommendations/data-model-and-migrations.md`](./recommendations/data-model-and-migrations.md)
4. [`recommendations/frontend-ia-and-flow-spec.md`](./recommendations/frontend-ia-and-flow-spec.md)
5. [`recommendations/authn-sso-group-sync-spec.md`](./recommendations/authn-sso-group-sync-spec.md)
6. [`recommendations/provisioning-mode-spec.md`](./recommendations/provisioning-mode-spec.md)
7. [`recommendations/scim-adoption-recommendation.md`](./recommendations/scim-adoption-recommendation.md)
8. [`recommendations/rollout-risk-and-observability.md`](./recommendations/rollout-risk-and-observability.md)
9. [`recommendations/bulk-user-endpoint-plan.md`](./recommendations/bulk-user-endpoint-plan.md)
10. [`recommendations/access-management-test-coverage-plan.md`](./recommendations/access-management-test-coverage-plan.md)
11. [`recommendations/frontend-access-first-class-plan.md`](./recommendations/frontend-access-first-class-plan.md)
12. [`recommendations/frontend-access-first-class-execution-plan.md`](./recommendations/frontend-access-first-class-execution-plan.md)
13. [`recommendations/documentation-final-resting-place-plan.md`](./recommendations/documentation-final-resting-place-plan.md)

### Reference Artifacts

1. [`reference/endpoint-matrix.md`](./reference/endpoint-matrix.md)
2. [`reference/permission-matrix.md`](./reference/permission-matrix.md)
3. [`reference/erd.mmd`](./reference/erd.mmd)
4. [`reference/sequence-diagrams.mmd`](./reference/sequence-diagrams.mmd)
5. [`reference/code-map.md`](./reference/code-map.md)
6. [`reference/bulk-user-acceptance-matrix.md`](./reference/bulk-user-acceptance-matrix.md)
7. [`reference/access-test-matrix.md`](./reference/access-test-matrix.md)
8. [`reference/access-ui-flow-maps.mmd`](./reference/access-ui-flow-maps.mmd)
9. [`reference/access-ui-state-matrix.md`](./reference/access-ui-state-matrix.md)

## How to Use This Package

1. Use canonical docs for current runtime behavior.
2. Use this package for design rationale and decision provenance.
3. For UI redesign work, start with:
   - `research/access-ui-task-flows-entra-plus-peers.md`
   - `analysis/frontend-access-ui-gap-analysis.md`
   - `recommendations/frontend-access-first-class-execution-plan.md`
