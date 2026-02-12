# Access Management Redesign (Hard Cutover)

Date: February 11, 2026

This package contains the analysis and recommendations for a first-class, normalized access model across organization and workspace settings, with future-ready group support and Graph-aligned API patterns.

## Scope and Constraints

- Hard cutover release (no `/v2` API family).
- Design for three principal outcomes:
  1. User outcome: simple, predictable access flows.
  2. Admin outcome: consistent and auditable controls.
  3. Developer outcome: normalized, maintainable code and API boundaries.
- Keep UI clean and uncluttered: one primary table + one drawer pattern per access surface.

## Recommended Direction (Decision Summary)

- Adopt a principal-aware model (`user` and `group`) for role assignments at organization and workspace scopes.
- Make invitation-driven provisioning the default for workspace-scoped creation so workspace owners can invite/create users without global user-admin privileges.
- Add groups with both `assigned` and `dynamic` membership modes:
  - `assigned`: ADE-managed membership.
  - `dynamic`: provider-managed membership (read-only in ADE for first cut).
- Normalize backend and frontend routes into a consistent `access` information architecture.
- Align API semantics with Microsoft Graph-style resources and membership `$ref` operations where practical.

## Package Index

### Research

- [`research/codebase-current-state.md`](./research/codebase-current-state.md)
- [`research/ui-playwright-audit.md`](./research/ui-playwright-audit.md)
- [`research/industry-patterns.md`](./research/industry-patterns.md)
- [`research/graph-entra-scim-standards.md`](./research/graph-entra-scim-standards.md)

### Analysis

- [`analysis/problem-statement.md`](./analysis/problem-statement.md)
- [`analysis/option-matrix.md`](./analysis/option-matrix.md)
- [`analysis/workspace-owner-user-creation-options.md`](./analysis/workspace-owner-user-creation-options.md)
- [`analysis/group-membership-models.md`](./analysis/group-membership-models.md)
- [`analysis/rbac-composition-models.md`](./analysis/rbac-composition-models.md)

### Recommendations

- [`recommendations/target-model.md`](./recommendations/target-model.md)
- [`recommendations/api-routes-hard-cutover.md`](./recommendations/api-routes-hard-cutover.md)
- [`recommendations/data-model-and-migrations.md`](./recommendations/data-model-and-migrations.md)
- [`recommendations/frontend-ia-and-flow-spec.md`](./recommendations/frontend-ia-and-flow-spec.md)
- [`recommendations/authn-sso-group-sync-spec.md`](./recommendations/authn-sso-group-sync-spec.md)
- [`recommendations/rollout-risk-and-observability.md`](./recommendations/rollout-risk-and-observability.md)

### Reference Artifacts

- [`reference/endpoint-matrix.md`](./reference/endpoint-matrix.md)
- [`reference/permission-matrix.md`](./reference/permission-matrix.md)
- [`reference/erd.mmd`](./reference/erd.mmd)
- [`reference/sequence-diagrams.mmd`](./reference/sequence-diagrams.mmd)
- [`reference/code-map.md`](./reference/code-map.md)

## How to Use This Package

1. Read the current-state and standards research first.
2. Review the option matrix and decision analyses.
3. Adopt the single recommended model in `recommendations/`.
4. Use `reference/` as implementation input (API contracts, permissions, data relationships, and flows).

## Decision Status

- Recommendation status: `proposed-final`
- Open decision count after this package: `0` (implementation-ready)

