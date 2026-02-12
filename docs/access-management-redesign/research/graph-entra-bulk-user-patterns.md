# Graph / Entra Bulk User Patterns

This document captures Microsoft Graph and Entra conventions relevant to bulk user create/update/delete behavior.

## 1. Graph user CRUD is resource-oriented (single-user per request)

Microsoft Graph documents user lifecycle as standard resource operations:

- `POST /users` for create.
- `PATCH /users/{id|userPrincipalName}` for update.
- `DELETE /users/{id|userPrincipalName}` for delete.

Sources:

- [Create user (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/user-post-users?view=graph-rest-1.0)
- [Update user (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/user-update?view=graph-rest-1.0)
- [Delete user (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/user-delete?view=graph-rest-1.0)
- [Working with users in Microsoft Graph](https://learn.microsoft.com/en-us/graph/api/resources/users?view=graph-rest-1.0)

Implication for ADE:

1. Graph does not define a dedicated `/users/bulkCreate` style API.
2. Graph bulk behavior is modeled through JSON batching.

## 2. Graph standard bulk mechanism is JSON batching (`/$batch`)

Microsoft Graph supports combining multiple operations in a single call via `POST /$batch` with a request envelope:

- `requests[]` list
- each request has `id`, `method`, `url`, optional `headers`, optional `body`
- server returns `responses[]` with per-request status and payload
- maximum 20 requests per batch
- request dependencies can be modeled with `dependsOn`

Source:

- [Combine multiple HTTP requests using JSON batching](https://learn.microsoft.com/en-us/graph/json-batching)

Implication for ADE:

1. A Graph-aligned bulk API should prefer one batch envelope endpoint over bespoke per-action bulk endpoints.
2. Request-level success/failure should be explicit (partial success is normal).
3. Dependency-aware execution should be supported where cross-request ordering matters.

## 3. Throttling and retry semantics in batched operations

Graph throttling guidance notes that batched subrequests are evaluated independently and can return mixed outcomes (for example `429` on some items even when the batch call itself succeeds).

Source:

- [Microsoft Graph throttling guidance](https://learn.microsoft.com/en-us/graph/throttling)

Implication for ADE:

1. Batch response must preserve per-item status and retry hints.
2. Clients should retry only failed operations, not blindly replay successful ones.

## 4. SDK behavior and request chunking conventions

Microsoft Graph SDK documentation notes automatic request splitting for batches over 20 items.

Source:

- [Use the Microsoft Graph SDKs to batch requests](https://learn.microsoft.com/en-us/graph/sdks/batch-requests?tabs=python)

Implication for ADE:

1. Publish a first-party chunking helper for UI/backend clients.
2. Set clear server-side limits and predictable validation errors for oversize batches.

## 5. Entra and SCIM `/Bulk` context

Relevant standards/Entra guidance:

1. RFC 7644 defines `/Bulk` as an optional SCIM protocol feature.
2. Entra SCIM guidance indicates `/Bulk` is not currently supported by the Entra provisioning service.

Sources:

- [RFC 7644 (SCIM Protocol)](https://datatracker.ietf.org/doc/html/rfc7644)
- [Tutorial: develop and plan provisioning for a SCIM endpoint in Microsoft Entra ID](https://learn.microsoft.com/en-us/entra/identity/app-provisioning/use-scim-to-provision-users-and-groups)

Implication for ADE:

1. Keep SCIM `/scim/v2/Bulk` out of initial scope.
2. Implement bulk admin operations in ADE application API (`/api/v1`) using Graph-style batch envelope semantics.

## ADE Guidance Derived from Research

1. Use `POST /api/v1/$batch` as the canonical bulk surface.
2. Limit batch size to 20 requests to mirror Graph and reduce operational surprises.
3. Enforce per-subrequest authorization and audit events.
4. Support partial success by design with deterministic per-item error objects.
5. Keep SCIM focused on interoperable user/group provisioning endpoints, not SCIM `/Bulk`.
