# Group Membership Models

## Goal

Define a group model that supports immediate operational needs and future IdP-driven scale without introducing bespoke behavior.

## Membership Modes

### 1. Assigned (explicit)

- Membership is directly managed in ADE.
- CRUD operations use membership reference endpoints (`$ref` style).
- Best for app-local teams and exceptions.

### 2. Dynamic (rule-driven)

- Membership is derived externally by identity provider (Entra/Okta/etc.) and synced into ADE.
- ADE treats membership as read-only for this mode in first cut.
- No internal dynamic rule engine in first cut.

## Group Source Types

1. `internal`: created and managed in ADE.
2. `idp`: imported/synced from external provider.

## Combined Model (Recommended)

- `membership_mode=assigned` supports manual membership operations.
- `membership_mode=dynamic` disallows manual add/remove in ADE.
- `source=idp` groups use `external_id` and sync metadata for reconciliation.

## Why this model

1. Matches Entra dynamic-group behavior and Graph conventions.
2. Prevents rule conflicts from dual control (ADE + IdP) on dynamic groups.
3. Keeps first release implementation bounded and predictable.
4. Provides direct path to future SCIM + IdP sync support.

## Operational Rules (Recommended)

1. Direct membership changes (`POST/DELETE .../members/$ref`) allowed only when:
   - group `membership_mode=assigned`
   - actor has group membership manage permission in scope
2. Dynamic group memberships are updated only by sync jobs/webhooks.
3. Effective access is always union of:
   - direct user assignments
   - group assignments
   - transitive memberships (if enabled later)
4. User deactivation hard-blocks access regardless of group memberships.

## Out-of-Scope for First Cut

1. Nested groups.
2. Internal rule builder/executor for dynamic groups.
3. Multi-provider conflict resolution across overlapping group objects.

