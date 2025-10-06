# ADE Database Schema Reference

This document is the authoritative reference for ADE's relational schema. It captures the tables, enums, and rules that govern how workspaces, documents, configurations, and jobs relate to each other.

## Conventions
- Database dialect: PostgreSQL (SQLite used for local dev; follow the same logical structure).
- Naming: plural table names, `snake_case` columns, `_id` suffix for identifiers, `_at` suffix for timestamps.
- Timestamps: use `TIMESTAMPTZ` with millisecond precision.
- Identifiers: 26-character ULIDs unless noted. Surrogate keys are preferred over composite primaries for consistency.
- All tenant-scoped rows include a `workspace_id` and enforce referential integrity back to `workspaces`.

## Enums
- `user_system_role`: `admin | user`
- `workspace_role`: `owner | admin | member | viewer`
- `job_status`: `pending | running | succeeded | failed | canceled`
- `configuration_state`: `draft | active | archived`

## Core Tables

### users
Stores people and service accounts.
- `user_id` (PK), `email`, `email_canonical`, `password_hash` (nullable), `display_name`, `description`, `is_service_account`, `is_active`, `system_role` (enum), `last_login_at`, `created_by_user_id` (FK to `users`).
- Relationships: `workspace_memberships`, `user_identities`, `api_keys`, `configurations.published_by_user_id`.

### user_identities
Normalized SSO identities.
- `identity_id` (PK), `user_id` (FK to `users`), `provider` (FK to `identity_providers`), `subject`, `email_at_provider`, timestamps.
- Unique `(provider, subject)` ensures no duplicates.

### identity_providers
Catalog of configured SSO providers.
- `provider_id` (PK, slug), `label`, `icon_url`, `start_url`, `enabled`, `sort_order`, timestamps.
- Drives `/auth/providers` API and admin tooling.

### workspaces
Tenant boundary for all data.
- `workspace_id` (PK), `name`, `slug` (unique), `settings` (JSONB), `created_by_user_id` (FK to `users`), `archived_at`, timestamps.

### workspace_memberships
Connects users to workspaces.
- `workspace_membership_id` (PK), `workspace_id` (FK), `user_id` (FK), `role` (enum), `is_default`, timestamps.
- Constraints: unique `(user_id, workspace_id)` plus partial unique index on `(user_id) WHERE is_default = TRUE` enforcing a single default workspace per user.

### document_types
Global registry of supported document categories.
- `document_type_key` (PK, e.g. `invoice`), `display_name`, `description`, `icon_url`, `is_deprecated`.

### workspace_document_types
Optional workspace-specific metadata for document types.
- `workspace_document_type_id` (PK), `workspace_id` (FK), `document_type_key` (FK), `display_name_override`, `sort_order`, `is_visible`, timestamps.
- Unique `(workspace_id, document_type_key)`.

### configurations
Versioned extraction instructions.
- `configuration_id` (PK), `workspace_id` (FK), `document_type_key` (FK), `title`, `version` (integer scoped to workspace+doc type), `state` (enum), `activated_at`, `published_by_user_id` (FK to `users`), `published_at`, `revision_notes`, `payload` (JSONB), timestamps.
- Constraints: unique `(workspace_id, document_type_key, version)` and filtered unique index enforcing at most one `state = 'active'` per `(workspace_id, document_type_key)`.

### documents
Uploaded source files.
- `document_id` (PK), `workspace_id` (FK), metadata (`original_filename`, `content_type`, `byte_size`, `sha256`, `stored_uri`, `metadata` JSONB), retention fields (`expires_at`, `deleted_at`, `deleted_by_user_id`, `delete_reason`), `produced_by_job_id` (nullable FK to `jobs`), timestamps.
- Unique `(workspace_id, sha256)` prevents duplicates within a workspace.

### jobs
Processing runs that turn documents into tables.
- `job_id` (PK), `workspace_id` (FK), `configuration_id` (FK), `input_document_id` (FK), `status` (enum), `created_by_user_id` (FK), lifecycle timestamps (`queued_at`, `started_at`, `finished_at`), `attempt`, `parent_job_id` (self-FK), `priority`, `metrics` (JSONB), `logs` (JSONB), `error_code`, `error_message`, timestamps.
- Composite unique `(job_id, workspace_id)` plus composite FKs from dependent tables to enforce tenant safety.

### system_settings
Key/value store for global toggles.
- `key` (PK, e.g. `auth.force_sso`), `value` (JSONB), timestamps.

## Derived Views

### v_document_type_summary
Provides workspace-aware document type state:
- Columns: `workspace_id`, `document_type_key`, `display_name`, `status` (`active | draft | empty`), `active_configuration_id`, `version`.
- Definition joins `workspace_document_types` with `document_types` and summarizes `configurations` using correlated subqueries.

## Integrity Rules
- Every tenant-scoped table includes a `workspace_id` FK to enforce isolation.
- Jobs reference a single configuration version via `configuration_id`; `document_type` and `configuration_version` are not stored redundantly.
- Service code must set exactly one default membership per user; the database constraint ensures drift cannot occur.
- Only one active configuration per `(workspace, document_type)` enforced via filtered unique index.
## Operational Notes
- Use deterministic ULIDs for IDs during seeding/tests to simplify fixtures.
- When adding new tenant-scoped tables, include both the FK to `workspaces` and supporting indexes on `(workspace_id, created_at)` for pagination.
- Metrics endpoints should source throughput and success rates from `jobs` lifecycle timestamps; avoid duplicating aggregates in separate tables until necessary.
- System settings keys should follow a dotted namespace (`auth.force_sso`). Values stored as JSONB for flexibility but read through typed config helpers.

## Next Steps
This schema refactor requires aligning ORM models, repositories, and API contracts. Refer to `agents/SCHEMA_REFACTOR_PLAN.md` for the implementation work package.
