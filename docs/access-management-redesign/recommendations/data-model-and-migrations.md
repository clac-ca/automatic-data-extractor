# Data Model and Migrations (Hard Cutover)

## Goals

1. Replace user-only access grants with principal-aware assignments.
2. Add first-class groups and memberships.
3. Expand user profile schema for common AD/Entra fields.
4. Preserve auditability and sync readiness.

## Target Schema Changes

## 1. `users` table extensions

Add nullable columns:

- `given_name`
- `surname`
- `job_title`
- `department`
- `office_location`
- `mobile_phone`
- `business_phones` (JSON/text array)
- `employee_id`
- `employee_type`
- `preferred_language`
- `city`
- `state`
- `country`
- `source` (`internal|idp|scim`)
- `external_id` (IdP/SCIM correlation key)
- `last_synced_at`

Constraints:

- Unique index on `(source, external_id)` when `external_id` is not null.

## 2. `groups` (new)

Columns:

- `id` (UUID)
- `display_name`
- `slug`
- `description`
- `membership_mode` (`assigned|dynamic`)
- `source` (`internal|idp`)
- `external_id` (nullable)
- `is_active`
- `created_at`, `updated_at`

Constraints:

- Unique `slug`
- Unique `(source, external_id)` when `external_id` is not null

## 3. `group_memberships` (new)

Columns:

- `id` (UUID)
- `group_id`
- `user_id`
- `membership_source` (`internal|idp_sync`)
- `created_at`, `updated_at`

Constraints:

- Unique `(group_id, user_id)`
- FK to `groups`, FK to `users`

## 4. `role_assignments` (new normalized table)

Replace `user_role_assignments` with:

- `id` (UUID)
- `principal_type` (`user|group`)
- `principal_id` (UUID)
- `role_id` (UUID)
- `scope_type` (`organization|workspace`)
- `scope_id` (UUID nullable; null for organization)
- `created_at`

Constraints:

- Unique `(principal_type, principal_id, role_id, scope_type, scope_id)`
- FK `role_id -> roles.id`
- check constraint: `scope_type=organization => scope_id is null`
- check constraint: `scope_type=workspace => scope_id is not null`

## 5. `invitations` (new)

Columns:

- `id` (UUID)
- `email_normalized`
- `invited_user_id` (nullable FK users)
- `status` (`pending|accepted|expired|cancelled`)
- `invited_by_user_id`
- `expires_at`
- `redeemed_at`
- `metadata` (JSON: workspace context, role seed)
- `created_at`, `updated_at`

## Migration Strategy (Hard Cutover)

### Phase 0: Preflight checks

1. Snapshot DB.
2. Export current role assignments and workspace memberships.
3. Verify no orphaned `user_role_assignments` rows.

### Phase 1: Additive schema deployment

1. Add new tables (`groups`, `group_memberships`, `role_assignments`, `invitations`).
2. Add new user profile columns.
3. Keep old routes disabled until app cutover deploy.

### Phase 2: Backfill and transform

1. Backfill `role_assignments` from `user_role_assignments`:
   - `principal_type='user'`
   - `principal_id=user_id`
   - `scope_type='organization'` when `workspace_id is null`
   - `scope_type='workspace'` and `scope_id=workspace_id` otherwise
2. Validate assignment counts and unique constraints.
3. Maintain `workspace_memberships` only for workspace preference/default behavior (not RBAC grant source).

### Phase 3: Application cutover

1. Deploy backend using only new assignment model and new routes.
2. Deploy frontend route/IA cutover in same release.
3. Start writing audit events for invitations/group changes.

### Phase 4: Cleanup

1. Drop `user_role_assignments` after verification window.
2. Remove obsolete route handlers and frontend hooks.
3. Regenerate API types.

## Data Integrity and Audit Requirements

1. Every create/delete assignment action writes structured audit events.
2. Invitation lifecycle transitions are auditable.
3. Group sync updates include source event correlation IDs.
4. Deactivated users are excluded from effective-access materialization/evaluation.

## Rollback Considerations

- Because this is hard cutover, rollback must restore DB snapshot and previous app image as a pair.
- Keep migration scripts reversible where possible, but plan operational rollback at deployment level.

