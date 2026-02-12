# Provisioning Mode Option Matrix

Scoring scale: `1 (poor)` to `5 (strong)`.

Criteria:

- `Security`: least privilege, predictable lifecycle boundaries
- `Admin Clarity`: understandable operations for org admins
- `Standards`: alignment with SCIM/OIDC industry conventions
- `Maintainability`: implementation and runtime simplicity
- `Access Freshness`: how quickly membership/access reflects IdP changes

## Options

| Option | Security | Admin Clarity | Standards | Maintainability | Access Freshness | Notes |
|---|---:|---:|---:|---:|---:|---|
| A. Keep current mixed model (JIT + background full group sync) | 3 | 2 | 3 | 2 | 4 | Works but blends provisioning and sync concerns; harder to reason about |
| B. `disabled | jit | scim` modes, JIT sign-in hydration only (recommended) | 5 | 5 | 5 | 5 | 4 | Clear operating model; no implicit user creation from background group data |
| C. SCIM-only, remove JIT | 4 | 3 | 5 | 4 | 5 | Strong enterprise fit, weak for teams that cannot deploy SCIM |
| D. JIT-only, no SCIM | 2 | 4 | 2 | 4 | 3 | Simple but not enterprise-standard for lifecycle governance |

## Decision

Choose **Option B**.

### Why

1. Preserves flexibility for smaller teams (`disabled`/`jit`) and enterprises (`scim`).
2. Keeps behavior explicit and testable by mode.
3. Removes the most confusing failure mode: background group sync creating/altering identities indirectly.
4. Aligns with mainstream IdP guidance that SCIM is provisioning, OIDC sign-in is authentication.

## Rejected Tradeoffs

1. Option C was rejected because it blocks organizations that cannot enable SCIM.
2. Option D was rejected because it leaves ADE non-standard for enterprise provisioning.
3. Option A was rejected because it retains operational complexity and ambiguous ownership.
