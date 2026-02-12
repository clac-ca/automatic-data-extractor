# Batch Route Expansion Candidates (Graph-Aligned)

Date: February 12, 2026

## Summary

Current `POST /api/v1/$batch` is implemented as a user-only allowlist.  
The next step is to expand it to a broader **access-management batch surface** and retire bespoke patterns where standard batch transport is a better fit.

## Standards Baseline

1. Graph uses one JSON batch transport endpoint (`POST /$batch`) with per-item `id`, `method`, `url`, optional `headers`, optional `body`.
2. Graph keeps a practical 20 subrequest limit per batch.
3. Graph supports `dependsOn` and item-level `424` dependency behavior.
4. Graph treats throttling per subrequest (batch can be `200` while items fail with `429`).
5. Graph guidance recommends choosing fully sequential or fully parallel execution strategy per batch.

Sources:

- [Microsoft Graph JSON batching](https://learn.microsoft.com/en-us/graph/json-batching)
- [Microsoft Graph throttling and batching](https://learn.microsoft.com/en-us/graph/throttling)

## Current ADE Batch/Batch-Like Surfaces

1. `POST /api/v1/$batch` (Graph-style envelope, currently user lifecycle only)
2. `POST /api/v1/workspaces/{workspaceId}/documents/batch/tags` (bespoke)
3. `POST /api/v1/workspaces/{workspaceId}/documents/batch/delete` (bespoke)
4. `POST /api/v1/workspaces/{workspaceId}/documents/batch/restore` (bespoke)
5. `POST /api/v1/workspaces/{workspaceId}/runs/batch` (specialized all-or-nothing workflow)

## Access-Management Expansion Candidates for `/$batch`

Scoring scale: `1 (low)` to `5 (high)`.

| Candidate subrequest | Existing route | Graph/standard fit | Product value | Complexity | Recommendation |
|---|---|---:|---:|---:|---|
| `POST /groups/{groupId}/members/$ref` | Group membership add | 5 | 5 | 2 | Add in next phase |
| `DELETE /groups/{groupId}/members/{memberId}/$ref` | Group membership remove | 5 | 5 | 2 | Add in next phase |
| `POST /roleAssignments` | Org assignment create | 4 | 5 | 3 | Add in next phase |
| `POST /workspaces/{workspaceId}/roleAssignments` | Workspace assignment create | 4 | 5 | 3 | Add in next phase |
| `DELETE /roleAssignments/{assignmentId}` | Assignment delete | 4 | 4 | 3 | Add in next phase |
| `POST /invitations` | Invite + optional workspace role seed | 4 | 4 | 3 | Add in next phase |
| `POST /invitations/{invitationId}/resend` | Invite lifecycle action | 4 | 3 | 2 | Add after invitation-create batching |
| `POST /invitations/{invitationId}/cancel` | Invite lifecycle action | 4 | 3 | 2 | Add after invitation-create batching |
| `POST /groups` | Group create | 4 | 3 | 2 | Add in later wave |
| `PATCH /groups/{groupId}` | Group update | 4 | 3 | 2 | Add in later wave |
| `DELETE /groups/{groupId}` | Group delete | 4 | 3 | 2 | Add in later wave |
| `POST /roles` / `PATCH /roles/{roleId}` / `DELETE /roles/{roleId}` | Role definition management | 3 | 2 | 4 | Defer (less frequent, ETag and policy complexity) |

## Why These Are Strong Candidates

1. Group membership `$ref` operations mirror Graph patterns directly and are the highest-volume admin tasks.
2. Role-assignment create/delete is core to permission administration and already normalized in ADE.
3. Invitation creation batched with assignment operations enables clean bulk onboarding flows without introducing SCIM `/Bulk`.
4. These operations are idempotent or safely conflict-detectable (`404/409/422`), which fits partial-success batch semantics.

Relevant standards anchors:

- [Create invitation (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/invitation-post?view=graph-rest-1.0)
- [Add group members by reference (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/group-post-members?view=graph-rest-1.0)
- [Remove group member reference (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/group-delete-members?view=graph-rest-1.0)
- [Create role assignment (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/rbacapplication-post-roleassignments?view=graph-rest-1.0)
- [Delete role assignment (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/rbacapplication-delete-roleassignments?view=graph-rest-1.0)

## Existing Batch Code to Replace

Current `BatchService` is hard-coded to user operations and one global permission check shape.  
To scale cleanly, replace parser/dispatcher code with a registry-based executor:

1. Define a `BatchOperationDefinition` registry (`method`, path-template matcher, permission evaluator, executor function).
2. Register user, group-membership, role-assignment, and invitation operations in one place.
3. Evaluate authz per item using each operation’s native permission rule (not a global blanket check).
4. Keep dependency DAG, nested transaction isolation, and per-item response semantics unchanged.
5. Keep envelope contract stable (`requests[]`, `responses[]`, `dependsOn`, max 20).

## Recommendation on Existing Bespoke Batch Routes

### Replace with `/$batch` (good fit)

1. `POST /api/v1/workspaces/{workspaceId}/documents/batch/tags`
2. `POST /api/v1/workspaces/{workspaceId}/documents/batch/delete`
3. `POST /api/v1/workspaces/{workspaceId}/documents/batch/restore`

Reason: these are transport-level batching concerns and have clear per-document single-resource counterparts.

### Keep specialized (not a pure transport concern)

1. `POST /api/v1/workspaces/{workspaceId}/runs/batch`

Reason: this endpoint is an orchestration workflow (prepare + enqueue) with intentional all-or-nothing semantics, not just N independent CRUD mutations.

## Explicit Non-Candidates (Current)

1. `/api/v1/admin/scim/tokens*`
   - Security-sensitive, low-volume credential lifecycle operations; batching increases blast radius with little operational gain.
2. `/api/v1/admin/settings`
   - Singleton configuration mutation; batch semantics do not improve UX or maintainability.
3. `/api/v1/auth*` session/login/logout endpoints
   - Authentication flows should remain explicit and independently auditable.

## Proposed Expansion Order

1. Expand `/$batch` to group-membership and role-assignment mutations.
2. Expand `/$batch` to invitation mutations.
3. Expand `/$batch` to group CRUD.
4. Converge document bespoke batch endpoints into `/$batch` in a separate non-access API normalization effort.
5. Keep `runs/batch` as specialized job API.

## Risks and Guardrails

1. Mixed-scope permission bugs:
   - Guardrail: enforce per-subrequest authz and include subrequest scope in audit logs.
2. Large batch latency:
   - Guardrail: keep max 20 and enforce timeout budget per item.
3. Hidden coupling between dependent operations:
   - Guardrail: preserve explicit `dependsOn` and deterministic `424`.
4. Client retry mistakes:
   - Guardrail: document retry-failed-items-only behavior and preserve per-item correlation ids.
