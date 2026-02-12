# Option Matrix

Scoring scale: `1 (poor)` to `5 (strong)`.

Criteria:

- `UX`: clarity and reduced friction for users/admins
- `Policy`: permission-boundary safety
- `Standards`: alignment with Graph/Entra/SCIM conventions
- `Maintainability`: long-term code and API simplicity
- `Cutover Risk`: feasibility in a hard-cutover release

## Decision A: Workspace owner creates users without org user-admin permission

| Option | UX | Policy | Standards | Maintainability | Cutover Risk | Notes |
|---|---:|---:|---:|---:|---:|---|
| A1. Keep create-user global only | 2 | 5 | 2 | 3 | 4 | Secure but fails delegated-admin requirement |
| A2. Let workspace owners call global `/users` create | 3 | 1 | 2 | 2 | 3 | Over-privileged, high blast radius |
| A3. Invitation resource with workspace context (recommended) | 5 | 5 | 5 | 5 | 4 | Clean boundary: invite + assign in one flow |

Decision: `A3`

## Decision B: Group membership model

| Option | UX | Policy | Standards | Maintainability | Cutover Risk | Notes |
|---|---:|---:|---:|---:|---:|---|
| B1. No groups in first cut | 2 | 3 | 1 | 3 | 5 | Defers core scaling requirement |
| B2. Assigned groups only | 4 | 4 | 3 | 4 | 4 | Good start, but weak IdP readiness |
| B3. Assigned + provider-managed groups (recommended) | 5 | 5 | 5 | 5 | 4 | Matches Entra/SCIM model without internal rule engine |
| B4. Full internal dynamic rules engine now | 3 | 3 | 4 | 2 | 1 | Too complex for hard cutover |

Decision: `B3`

## Decision C: RBAC composition (org roles + workspace roles + groups)

| Option | UX | Policy | Standards | Maintainability | Cutover Risk | Notes |
|---|---:|---:|---:|---:|---:|---|
| C1. Keep user-only assignments | 2 | 3 | 1 | 2 | 5 | Blocks group-derived access |
| C2. Add separate group-assignment table only | 3 | 3 | 2 | 2 | 3 | Duplicated logic and drift risk |
| C3. Principal-aware assignments (`principal_type`, `principal_id`) (recommended) | 5 | 5 | 5 | 5 | 4 | Single evaluator and clean expansion |

Decision: `C3`

## Decision D: API route strategy in hard cutover

| Option | UX | Policy | Standards | Maintainability | Cutover Risk | Notes |
|---|---:|---:|---:|---:|---:|---|
| D1. Keep mixed legacy routes | 2 | 3 | 2 | 1 | 5 | Lowest immediate risk, highest long-term cost |
| D2. Partial normalization | 3 | 4 | 3 | 3 | 3 | Leaves conceptual seams |
| D3. Full normalized cutover with SCIM add-on (recommended) | 5 | 5 | 5 | 5 | 3 | Highest long-term coherence |

Decision: `D3`

## Decision E: Frontend information architecture

| Option | UX | Policy | Standards | Maintainability | Cutover Risk | Notes |
|---|---:|---:|---:|---:|---:|---|
| E1. Keep existing org/workspace split taxonomy | 2 | 4 | 2 | 2 | 5 | Continues user confusion |
| E2. Unified `access` taxonomy, preserve shell patterns (recommended) | 5 | 5 | 5 | 5 | 4 | Highest continuity with low visual churn |
| E3. Full redesign with new component library | 4 | 4 | 4 | 2 | 1 | Too risky for hard cutover timeline |

Decision: `E2`

## Decision F: Provisioning mode and group update strategy

| Option | UX | Policy | Standards | Maintainability | Cutover Risk | Notes |
|---|---:|---:|---:|---:|---:|---|
| F1. JIT + full background tenant sync | 3 | 3 | 3 | 2 | 4 | Functional but ambiguous ownership |
| F2. SCIM-only (remove JIT) | 3 | 5 | 5 | 4 | 2 | Strong enterprise fit, excludes smaller teams |
| F3. Explicit `disabled|jit|scim` with JIT sign-in hydration only (recommended) | 5 | 5 | 5 | 5 | 4 | Clear model, simple runtime, broad deployability |

Decision: `F3`

## Final Decision Bundle

- `A3 + B3 + C3 + D3 + E2 + F3`

This bundle satisfies all three outcomes while keeping the architecture standards-aligned and simpler to reason about.
