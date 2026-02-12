# Graph / Entra / SCIM Standards Research

This document anchors the redesign to widely adopted identity-management standards and API conventions.

## 1. Microsoft Graph: Users

### Key conventions

- User lifecycle is first-class (`POST /users`, `PATCH /users/{id}`).
- User schema includes enterprise profile fields (`jobTitle`, `department`, `officeLocation`, `mobilePhone`, `businessPhones`, etc.).

Sources:

- [Create User (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/user-post-users?view=graph-rest-1.0)
- [User resource type (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0)

Implication for ADE:

- Keep ADE user schema aligned with common enterprise identity fields.

## 2. Microsoft Graph: Groups and Membership

### Key conventions

- Groups are first-class (`/groups`).
- Membership writes use reference endpoints:
  - `POST /groups/{groupId}/members/$ref`
  - `DELETE /groups/{groupId}/members/{memberId}/$ref`
- User-centric group traversal is available (`/users/{id}/memberOf`).

Sources:

- [Group resource type](https://learn.microsoft.com/en-us/graph/api/resources/group?view=graph-rest-1.0)
- [List group members](https://learn.microsoft.com/en-us/graph/api/group-list-members?view=graph-rest-1.0)
- [Add members (`$ref`)](https://learn.microsoft.com/en-us/graph/api/group-post-members?view=graph-rest-1.0)
- [User memberOf / transitiveMemberOf](https://learn.microsoft.com/en-us/graph/api/user-list-memberof?view=graph-rest-1.0)

Implication for ADE:

- Keep Graph-like membership semantics in ADE API (`$ref` routes) to avoid bespoke design.

## 3. Microsoft Graph: Invitations

### Key conventions

- Invitation is explicit (`POST /invitations`) and policy-aware.

Source:

- [Create invitation (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/invitation-post?view=graph-rest-1.0)

Implication for ADE:

- Workspace-owner onboarding should remain invitation-first, not hidden side effects.

## 4. OData Query Semantics

### Key conventions

- Graph list APIs use query parameters such as `$filter`, `$select`, `$orderby`, `$top`, `$count`.

Sources:

- [OData query parameters](https://learn.microsoft.com/en-us/graph/query-parameters)
- [Advanced queries](https://learn.microsoft.com/en-us/graph/aad-advanced-queries)

Implication for ADE:

- Keep ADE cursor pagination but allow predictable filter/sort behavior and optional Graph-like query aliasing.

## 5. Group Claims Overage and Runtime Membership Fetch

### Key conventions

- Large group sets may not fit reliably in tokens; Entra guidance calls out group overage and using Graph lookup patterns.

Source:

- [Configure group claims and app roles in tokens](https://learn.microsoft.com/en-us/security/zero-trust/develop/configure-tokens-group-claims-app-roles)

Implication for ADE:

- In JIT mode, membership hydration at sign-in should use user-specific Graph calls rather than trusting token group claims alone.

## 6. Entra Provisioning Guidance: Graph vs SCIM

### Key conventions

- Graph-based sync and SCIM-based provisioning are distinct integration models.
- SCIM is the standard protocol choice for app provisioning interoperability.

Sources:

- [Choose between Microsoft Graph and SCIM for user and group provisioning](https://learn.microsoft.com/en-us/entra/identity/app-provisioning/scim-graph-scenarios)
- [Use SCIM to provision users and groups](https://learn.microsoft.com/en-us/entra/identity/app-provisioning/use-scim-to-provision-users-and-groups)

Implication for ADE:

- Provide explicit provisioning-mode choice so operators know which channel is authoritative.

## 7. SCIM Protocol Requirements

### Key conventions

- Standard endpoint families include:
  - `/ServiceProviderConfig`
  - `/ResourceTypes`
  - `/Schemas`
  - `/Users`
  - `/Groups`
- Standard operations include filtering, pagination, and PATCH semantics.

Sources:

- [RFC 7644 SCIM Protocol](https://datatracker.ietf.org/doc/html/rfc7644)
- [RFC 7643 SCIM Core Schema](https://datatracker.ietf.org/doc/html/rfc7643)

Implication for ADE:

- If ADE ships SCIM, it should follow standard `/scim/v2` resource layout and behavior rather than custom provisioning routes.

## ADE Standards Checklist (Derived)

1. Principal-aware RBAC (`user|group`) with consistent org/workspace scope handling.
2. Invitation-first explicit onboarding flow for delegated workspace admins.
3. Provider-managed groups are read-only in ADE membership mutation endpoints.
4. Provisioning mode is explicit per organization: `disabled | jit | scim`.
5. JIT mode uses per-user sign-in membership hydration; no hidden tenant-wide user provisioning.
6. SCIM mode uses standards-shaped `/scim/v2` endpoints and becomes automated provisioning authority.

## 8. Graph Bulk Semantics

### Key conventions

1. Graph bulk request execution is modeled with `POST /$batch`, not user-specific bulk CRUD routes.
2. Graph batches have a practical limit of 20 subrequests with per-item status outcomes.
3. Graph supports subrequest dependencies (`dependsOn`) for ordered execution.
4. Throttling in batch is per-subrequest; clients retry failed items only.

Sources:

- [JSON batching](https://learn.microsoft.com/en-us/graph/json-batching)
- [Microsoft Graph throttling](https://learn.microsoft.com/en-us/graph/throttling)

Implication for ADE:

Use Graph-style `POST /api/v1/$batch` for bulk user operations and keep SCIM `/Bulk` out of initial scope.
