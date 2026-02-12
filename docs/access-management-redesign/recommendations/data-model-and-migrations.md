# Data Model and Migrations (Hard Cutover)

## Goals

1. Keep principal-aware access grants as the RBAC foundation.
2. Keep user/group schema compatible with Graph + SCIM attributes.
3. Support explicit provisioning modes without schema sprawl.
4. Keep migration path simple and operationally safe.

## Core Schema Shape

## 1. `users` table

Expected fields include:

- identity: `email`, `email_normalized`, `display_name`
- enterprise profile: `given_name`, `surname`, `job_title`, `department`, `office_location`, `mobile_phone`, `business_phones`, `employee_id`, `employee_type`, `preferred_language`, `city`, `state`, `country`
- lifecycle/source: `is_active`, `source`, `external_id`, `last_synced_at`

Notes:

- `source` should distinguish internal/JIT/SCIM ownership (`internal`, `idp`, `scim`).
- `external_id` should remain provider correlation key.

## 2. `groups` table

Expected fields include:

- `display_name`, `slug`, `description`
- `membership_mode` (assigned/provider-managed)
- `source` (`internal` or provider-managed)
- `external_id`, `is_active`

## 3. `group_memberships` table

Expected fields include:

- `group_id`, `user_id`
- `membership_source` (`internal` or provider-managed)
- uniqueness on `(group_id, user_id)`

## 4. `role_assignments` table

Principal-aware assignment shape:

- `principal_type`, `principal_id`
- `role_id`
- `scope_type`, `scope_id`
- scope consistency constraints and uniqueness across principal+role+scope

## 5. `invitations` table

Lifecycle model:

- `email_normalized`, `invited_user_id`, `invited_by_user_id`
- `status`, `expires_at`, `redeemed_at`, `metadata`

## 6. Provisioning mode storage

Provisioning mode is policy/config, not identity data.

Recommended storage:

- runtime settings payload (`application_settings.data.auth.identity_provider.provisioning_mode`)
- enum values: `disabled | jit | scim`

No standalone table is required for provisioning mode itself.

## Migration Constraint (Locked)

`0002_access_model_hard_cutover` has not been deployed yet. If schema updates are required for this redesign, update migration in place:

- `backend/src/ade_db/migrations/versions/0002_access_model_hard_cutover.py`

Do not create a new migration revision for this iteration.

## Migration Strategy

1. Keep migration idempotent and parity-checked.
2. Validate transformed assignment counts before app boot.
3. Keep rollback snapshot-based (downgrade script remains unsupported).

## Data Integrity and Audit Requirements

1. Every assignment mutation writes structured audit events.
2. Invitation transitions are auditable.
3. Provider-managed group changes record channel (`jit` hydration or `scim`).
4. Deactivated users are excluded from effective-access evaluation.
