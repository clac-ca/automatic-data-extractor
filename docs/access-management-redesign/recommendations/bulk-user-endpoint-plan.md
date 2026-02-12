# Bulk User Endpoint Plan (Graph-Aligned, Implementation-Ready)

## Summary

Add first-class bulk user lifecycle support using one Graph-style envelope endpoint while keeping ADE permission boundaries and provisioning modes intact.

Primary path:

1. `POST /api/v1/$batch`

This plan targets bulk create, bulk update, and bulk removal of access (via deactivate) for users.

## Decision Lock

1. Bulk semantics follow Graph `/$batch` structure.
2. Phase 1 scope is user lifecycle only.
3. "Bulk delete" maps to `POST /users/{userId}/deactivate` in current ADE policy.
4. No SCIM `/scim/v2/Bulk` in this phase.
5. No cross-item transaction atomicity.

## API Contract

## Endpoint

`POST /api/v1/$batch`

## Request envelope

```json
{
  "requests": [
    {
      "id": "1",
      "method": "POST",
      "url": "/users",
      "headers": {
        "Content-Type": "application/json"
      },
      "body": {
        "email": "user@example.com",
        "displayName": "Example User"
      }
    },
    {
      "id": "2",
      "method": "PATCH",
      "url": "/users/00000000-0000-0000-0000-000000000123",
      "body": {
        "department": "Finance"
      },
      "dependsOn": ["1"]
    }
  ]
}
```

## Response envelope

```json
{
  "responses": [
    {
      "id": "1",
      "status": 201,
      "headers": {
        "Location": "/api/v1/users/00000000-0000-0000-0000-000000000123"
      },
      "body": {
        "id": "00000000-0000-0000-0000-000000000123"
      }
    },
    {
      "id": "2",
      "status": 200,
      "body": {
        "id": "00000000-0000-0000-0000-000000000123",
        "department": "Finance"
      }
    }
  ]
}
```

## Allowed subrequests (phase 1)

1. `POST /users`
2. `PATCH /users/{userId}`
3. `POST /users/{userId}/deactivate`

Unsupported methods/URLs return subrequest `422`.

## Validation and execution semantics

1. `requests` length: `1..20`.
2. Subrequest `id` values must be unique within envelope.
3. URLs must be relative and allowlisted; absolute URLs rejected.
4. Subrequest body shape must match existing endpoint schema exactly.
5. `dependsOn` (optional) supports dependency sequencing; failed dependency yields `424` for downstream request.
6. Without dependencies, subrequests are treated as independent; clients must not rely on response order and must correlate by `id`.
7. Each subrequest executes in isolated transaction scope.
8. Envelope-level parse/shape errors fail fast; item-level business/auth errors remain per-item.

## Auth, RBAC, and CSRF

1. Top-level call requires authenticated session or valid API auth.
2. Batch mutating calls require CSRF in browser-session contexts, same as existing mutating user routes.
3. Each subrequest reuses existing permission checks (`users.manage_all`, etc.).
4. Batch does not grant extra authority; it is transport aggregation only.

## Error and retry model

## Envelope-level errors

1. `400` malformed envelope JSON/shape.
2. `413` payload too large.
3. `422` invalid dependency graph or unsupported envelope fields.

## Subrequest-level errors

1. `403` permission denied.
2. `404` user not found.
3. `409` duplicate/conflict (for example duplicate email create).
4. `422` validation failure.
5. `424` dependency failed.
6. `429` throttled.
7. `500` unexpected server failure.

## Retry guidance

1. Retry only failed subrequests.
2. Honor per-item `Retry-After` where present.
3. Use idempotent client behavior for create flows (dedupe by normalized email before retry when possible).

## Implementation plan

### Phase 1: Schemas and router

1. Add batch schemas:
   - request envelope
   - response envelope
   - subrequest and subresponse models
2. Add `features/batch/router.py` with `POST /$batch`.
3. Register router in `backend/src/ade_api/api/v1/router.py`.

### Phase 2: Batch executor

1. Add `features/batch/service.py` with:
   - URL/method allowlist validation
   - dependency graph validation/execution
   - per-subrequest dispatch into user service operations
2. Use isolated transaction boundaries per subrequest.
3. Preserve correlation metadata (`batch_id`, `subrequest_id`) in logs.

### Phase 3: Controls and observability

1. Reuse `backend/src/ade_api/common/rate_limit.py` for per-actor batch call caps.
2. Add batch metrics:
   - `access.batch.requests.count`
   - `access.batch.subrequests.count`
   - `access.batch.subrequests.failed`
   - `access.batch.latency`
3. Add structured logs for request and per-item outcomes.

### Phase 4: Frontend/client support

1. Add users API client helper in `frontend/src/api/users/api.ts`:
   - `batchUserMutations(requests)`
   - helper to chunk large sets into size-20 envelopes
2. Add UX-safe status presentation for partial success.
3. Regenerate OpenAPI and `frontend/src/types/generated/openapi.d.ts`.

### Phase 5: Tests

1. Add backend integration tests under `backend/tests/api/integration/users/`:
   - mixed success/failure envelope
   - permission-denied item among successful items
   - dependency failure `424`
   - max-size enforcement
2. Add backend unit tests for dependency graph and allowlist validation.
3. Add frontend unit tests for chunking and response correlation by subrequest `id`.

### Phase 6: Rollout

1. Ship with current single-user endpoints unchanged.
2. Keep bulk endpoint additive and backwards-compatible.
3. Monitor failure ratio and throttling before expanding to other resources.

## File-level work map

## Backend

1. `backend/src/ade_api/api/v1/router.py`
2. `backend/src/ade_api/features/batch/router.py` (new)
3. `backend/src/ade_api/features/batch/service.py` (new)
4. `backend/src/ade_api/features/batch/schemas.py` (new)
5. `backend/src/ade_api/features/users/service.py` (reuse helper methods if needed)
6. `backend/src/ade_api/common/rate_limit.py` (reuse for batch guardrail)
7. `backend/src/ade_api/openapi.json` (regenerate)

## Tests

1. `backend/tests/api/integration/users/test_users_batch_router.py` (new)
2. `backend/tests/api/unit/features/batch/test_batch_service.py` (new)

## Frontend

1. `frontend/src/api/users/api.ts`
2. `frontend/src/api/users/__tests__/api.test.ts`
3. `frontend/src/types/generated/openapi.d.ts`

## Non-goals (this phase)

1. Asynchronous bulk job orchestration.
2. Cross-resource batch mutation (groups/roles/assignments).
3. SCIM `/Bulk`.
4. Hard user-delete semantics.

## Definition of done

1. `POST /api/v1/$batch` live with Graph-style envelope and 20-item cap.
2. Bulk create/update/deactivate scenarios pass integration tests.
3. Per-subrequest authz and error semantics are deterministic.
4. Observability emits batch-level and item-level success/failure signals.
5. Frontend client can safely run chunked bulk user mutations.

## Source anchors

1. [JSON batching (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/json-batching)
2. [Microsoft Graph throttling](https://learn.microsoft.com/en-us/graph/throttling)
3. [Create user (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/user-post-users?view=graph-rest-1.0)
4. [Update user (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/user-update?view=graph-rest-1.0)
5. [Delete user (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/user-delete?view=graph-rest-1.0)
6. [Entra SCIM guidance (`/Bulk` note)](https://learn.microsoft.com/en-us/entra/identity/app-provisioning/use-scim-to-provision-users-and-groups)
7. [RFC 7644 (SCIM `/Bulk` optional)](https://datatracker.ietf.org/doc/html/rfc7644)
