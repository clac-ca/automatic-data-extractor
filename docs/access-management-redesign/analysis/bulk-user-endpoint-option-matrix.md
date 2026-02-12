# Bulk User Endpoint Option Matrix

Scoring scale: `1 (poor)` to `5 (strong)`.

Criteria:

- `Standards`: alignment with Graph/Entra patterns
- `Maintainability`: implementation complexity and long-term simplicity
- `Client Ergonomics`: ease of use for frontend/admin tooling
- `Safety`: fine-grained authz, auditability, and predictable failures
- `Scalability`: ability to handle high-volume operations over time

## Options

| Option | Standards | Maintainability | Client Ergonomics | Safety | Scalability | Notes |
|---|---:|---:|---:|---:|---:|---|
| A. Custom user-only bulk endpoints (`/users/batchCreate`, `/users/batchUpdate`, `/users/batchDelete`) | 2 | 3 | 4 | 4 | 3 | Easy to start but bespoke and less portable |
| B. Graph-style batch envelope (`POST /$batch`) constrained to user lifecycle operations (recommended) | 5 | 4 | 4 | 5 | 4 | Matches Graph mental model; one reusable execution surface |
| C. Async bulk-job APIs only (`/users/bulkJobs`) | 3 | 3 | 3 | 5 | 5 | Good for very large loads, slower and heavier for normal admin tasks |
| D. SCIM `/Bulk` for admin user lifecycle | 2 | 2 | 2 | 3 | 4 | Optional in SCIM and not Entra-first compatible in practice |

## Decision

Choose **Option B** now, with **Option C as future expansion** for very large imports.

### Why

1. Strongest standards alignment with Microsoft Graph bulk conventions (`/$batch`).
2. Keeps access-control and auditing logic centralized in existing resource handlers.
3. Avoids proliferation of action-specific bulk routes and payload schemas.
4. Supports partial success semantics expected by real admin operations.

## Rejected Tradeoffs

1. Option A was rejected because it creates ADE-specific API shapes that diverge from common enterprise patterns.
2. Option C was rejected as the primary design because it adds orchestration overhead for routine bulk edits.
3. Option D was rejected because SCIM `/Bulk` is optional and not the practical path for Entra provisioning.

## Additional Design Call

For ADE user offboarding, treat "bulk delete" as **bulk deactivation** in current contracts unless/until canonical `DELETE /users/{id}` is introduced.  
This keeps policy-safe identity retention while still providing bulk removal of effective access.

## Follow-on Analysis

Batch expansion beyond user lifecycle operations (groups, role assignments, invitations, and existing bespoke batch-route replacement candidates) is documented in:

- [`analysis/batch-route-expansion-candidates.md`](./batch-route-expansion-candidates.md)
