# RBAC Composition Models (Org + Workspace + Groups)

## Problem

ADE has two scopes of authorization (organization/global and workspace), and needs to incorporate both direct and group-derived grants.

## Composition Candidates

### Model 1: Scope-isolated roles, no cross-scope implication

- Global roles only grant global permissions.
- Workspace roles only grant workspace permissions.
- Pros: strict boundaries.
- Cons: requires explicit admin assignment in each workspace for platform admins.

### Model 2: Global super-admin override + scope-isolated normal roles (recommended)

- Normal behavior: scope-isolated.
- Exception: specific global admin capability implies full workspace manage access.
- Pros: practical operations, aligns with current ADE behavior where `workspaces.manage_all` implies workspace permissions.
- Cons: requires explicit documentation to avoid surprise.

### Model 3: Unified global role namespace that can grant workspace permissions directly

- Pros: fewer concepts.
- Cons: weak separation of duties, harder to reason about delegated workspace authority.

Decision: `Model 2`

## Recommended Evaluation Algorithm

Given `(user, workspace_id?)`:

1. If user is inactive: deny all non-public actions.
2. Collect direct user assignments for target scope.
3. Collect group memberships for user.
4. Collect group assignments for those groups in target scope.
5. Expand role permissions to permission keys.
6. Apply implication rules (for example `.manage -> .read`, explicit policy implications).
7. Apply global override policy for designated super-admin permissions.
8. Return effective permission set as union.

## Conflict Resolution

- First cut uses allow-only RBAC (no explicit deny rules).
- Deterministic rule: effective permissions = set union of all grants.
- If future deny semantics are introduced, define precedence explicitly (`deny > allow`) in a separate policy layer.

## Scope Rules

1. Organization assignments have `scope_type=organization`, `scope_id=null`.
2. Workspace assignments have `scope_type=workspace`, `scope_id=<workspaceId>`.
3. Role definitions are scope-constrained (`organization` or `workspace`).
4. Assignment validator blocks role-scope mismatch.

## Group Interaction Rules

1. Group roles can be assigned at organization or workspace scope.
2. Effective workspace access includes:
   - direct workspace assignments
   - group workspace assignments
   - optional global override from org-level super-admin policy
3. Deactivated users never retain effective access via groups.

## Why this composition works

- Preserves least privilege.
- Supports delegated workspace administration.
- Matches enterprise patterns where groups drive bulk access.
- Keeps permission computation tractable and testable.

