# Group Membership Models

## Goal

Define a group model that supports immediate operational needs and future IdP-driven scale without introducing bespoke behavior.

## Membership Modes

### 1. Assigned (explicit)

- Membership is directly managed in ADE.
- CRUD operations use membership reference endpoints (`$ref` style).
- Best for app-local teams and exceptions.

### 2. Provider-managed

- Membership is controlled by external identity authority.
- ADE treats membership as read-only for manual mutation endpoints.
- Updates come from:
  - JIT per-user sign-in hydration (when provisioning mode is `jit`)
  - SCIM group operations (when provisioning mode is `scim`)

## Group Source Types

1. `internal`: created and managed in ADE.
2. `idp`: created/managed by provider-backed channels (JIT hydration or SCIM).

## Combined Model (Recommended)

- Internal assigned groups support manual membership operations.
- Provider-managed groups disallow manual add/remove in ADE.
- `external_id` and sync metadata support reconciliation and audit.

## Why this model

1. Matches common Entra/SCIM ownership patterns.
2. Prevents dual-control conflicts (ADE + IdP) on provider-managed memberships.
3. Keeps runtime behavior simple by tying membership channel to provisioning mode.
4. Avoids full tenant polling complexity in JIT mode.

## Operational Rules (Recommended)

1. Direct membership changes (`POST/DELETE .../members/$ref`) allowed only when group is internally managed.
2. Provider-managed memberships are updated only by trusted identity channel.
3. Effective access is union of direct user assignments and group assignments.
4. User deactivation hard-blocks access regardless of group memberships.

## Out-of-Scope for First Cut

1. Nested groups.
2. Internal rule builder/executor for dynamic policies.
3. Multi-provider conflict resolution across overlapping group objects.
