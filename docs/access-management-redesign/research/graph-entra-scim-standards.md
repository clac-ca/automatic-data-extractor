# Graph / Entra / SCIM Standards Research

This document anchors the redesign to widely adopted identity-management standards and API conventions.

## 1. Microsoft Graph: Users

### Key conventions

- User creation is a first-class resource operation (`POST /users`).
- User schema supports enterprise profile fields such as `jobTitle`, `department`, `officeLocation`, `mobilePhone`, and `businessPhones`.

Sources:

- [Create User (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/user-post-users?view=graph-rest-1.0)
- [User resource type (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0)

Implication for ADE:

- Extend ADE `users` with common enterprise profile attributes now, even if some are initially nullable and IdP-synced later.

## 2. Microsoft Graph: Groups and Membership

### Key conventions

- Groups are first-class resources (`/groups`).
- Membership management uses reference endpoints:
  - `POST /groups/{groupId}/members/$ref`
  - `DELETE /groups/{groupId}/members/{memberId}/$ref`
- Graph also exposes membership reads (`/groups/{groupId}/members`) and user membership traversals (`/users/{id}/memberOf`, `/users/{id}/transitiveMemberOf`).

Sources:

- [Group resource type](https://learn.microsoft.com/en-us/graph/api/resources/group?view=graph-rest-1.0)
- [List group members](https://learn.microsoft.com/en-us/graph/api/group-list-members?view=graph-rest-1.0)
- [Add members (`$ref`)](https://learn.microsoft.com/en-us/graph/api/group-post-members?view=graph-rest-1.0)
- [User memberOf / transitiveMemberOf](https://learn.microsoft.com/en-us/graph/api/user-list-memberof?view=graph-rest-1.0)

Implication for ADE:

- Use Graph-like membership routes and semantics to avoid bespoke endpoint design.
- Store effective access as the union of direct and group-derived assignments.

## 3. Microsoft Graph: Invitations

### Key conventions

- Invitation is explicit (`POST /invitations`) and includes email and redirect context.
- Graph supports delegated invitation behavior (including non-admin usage under policy).

Source:

- [Create invitation (Microsoft Graph)](https://learn.microsoft.com/en-us/graph/api/invitation-post?view=graph-rest-1.0)

Implication for ADE:

- Workspace-owner “create user” should be modeled as an invitation resource with optional immediate workspace assignment.

## 4. OData Query Semantics (Graph)

### Key conventions

- Standard list behavior relies on OData-style operators (`$filter`, `$select`, `$orderby`, `$top`, `$count`, etc.).
- Advanced queries often require `ConsistencyLevel: eventual` plus `$count=true`.

Sources:

- [OData query parameters](https://learn.microsoft.com/en-us/graph/query-parameters)
- [Advanced queries](https://learn.microsoft.com/en-us/graph/aad-advanced-queries)

Implication for ADE:

- Keep ADE list APIs cursor-based but add Graph-like query compatibility where practical:
  - canonical filter keys
  - predictable sort behavior
  - explicit consistency semantics for complex filters.

## 5. Entra Dynamic Groups

### Key conventions

- Dynamic membership is rule-driven and distinct from assigned membership.
- Dynamic groups are provider-managed; manual membership operations are not equivalent to assigned groups.

Source:

- [Dynamic membership groups (Microsoft Entra)](https://learn.microsoft.com/en-us/entra/identity/users/groups-dynamic-membership)

Implication for ADE:

- Model group `membership_mode` as `assigned | dynamic`.
- For first cut, treat dynamic groups as read-only from ADE and sourced from IdP sync.

## 6. SCIM Provisioning Standards

### Key conventions

- SCIM defines interoperable user/group schemas and protocol operations.
- Core resources: `/Users`, `/Groups`, schema discovery, service provider configuration.
- Enterprise user extension supports attributes such as employee number and department.

Sources:

- [SCIM endpoint guidance (Microsoft Entra)](https://learn.microsoft.com/en-us/entra/identity/app-provisioning/use-scim-to-provision-users-and-groups)
- [RFC 7643 SCIM Core Schema](https://datatracker.ietf.org/doc/rfc7643/)
- [RFC 7644 SCIM Protocol](https://datatracker.ietf.org/doc/rfc7644/)

Implication for ADE:

- Keep internal model SCIM-compatible now so future SCIM inbound provisioning does not require another schema rewrite.
- Add stable external-id mapping on users/groups/memberships for IdP reconciliation.

## ADE Standards Checklist (Derived)

1. Resource-first APIs for users, groups, invitations, and role assignments.
2. Principal-aware grants (`user` and `group`) at both org and workspace scope.
3. `$ref` style group membership operations.
4. Invitation records with lifecycle state and audit metadata.
5. Dynamic groups: IdP-owned, read-only in ADE first cut.
6. SCIM/Entra-compatible identity fields and external IDs.

