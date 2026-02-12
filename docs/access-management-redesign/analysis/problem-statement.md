# Problem Statement

ADE currently exposes access management through two partially overlapping systems:

- Organization-level users/roles APIs and screens.
- Workspace-level member/role APIs and screens.

These systems are functionally useful but not normalized, causing UX friction, policy ambiguity, and avoidable implementation complexity.

## Core Problem

The product lacks a unified, principal-centric access model that cleanly separates:

1. Identity lifecycle (user/group/invitation).
2. Access assignment (role grants by scope).
3. Effective authorization (direct + inherited permissions).

Without this separation, UI flows and APIs diverge, and delegated administration (especially workspace-owner user creation) remains awkward.

## User-Facing Symptoms

1. User creation and permission assignment are split across different surfaces.
2. Workspace add-member flow assumes existing global directory users.
3. Identity context can degrade to UUID-only rendering in member lists/drawers.
4. Organization and workspace pages look related but behave differently.

## Admin Symptoms

1. Delegation boundaries are not explicit enough for “workspace owner can invite but not globally administer users.”
2. No first-class group model for scalable access administration.
3. Route/permission vocabulary drift increases governance risk.

## Developer Symptoms

1. Assignment model is user-only (`user_role_assignments`) and cannot express group grants.
2. API contracts for assignments are split across unrelated route families.
3. Frontend route and permission checks are inconsistent (`.view` vs `.read` mismatch).
4. Future Entra/SCIM sync requires schema expansion not currently present.

## Constraints

1. Hard cutover only (no parallel `/v2` route family).
2. Must align with standard patterns (Graph-style resources and membership references).
3. Must support both org RBAC and workspace RBAC, with deterministic composition.
4. Must prepare for groups:
   - assigned memberships
   - dynamic memberships (IdP-managed first cut)
5. UI must remain tasteful and minimal (no cluttered admin surface).

## Success Criteria

1. Users can be invited/created and assigned workspace access in one flow when appropriate.
2. Org and workspace access surfaces share a consistent mental model and component grammar.
3. RBAC can evaluate effective permissions from direct and group-derived grants.
4. APIs are normalized, discoverable, and implementation-ready for AD/Entra profile fields and future sync.

