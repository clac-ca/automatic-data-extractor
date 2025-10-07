# ADE Database Schema Reference

This document is the authoritative reference for ADE's relational schema. It captures the tables, enums, and rules that govern how workspaces, documents, configurations, and jobs relate to each other.

## Conventions
- Database dialect: PostgreSQL (SQLite used for local dev; follow the same logical structure).
- Naming: plural table names, `snake_case` columns, `_id` suffix for identifiers, `_at` suffix for timestamps.
- Timestamps: use `TIMESTAMPTZ` with millisecond precision.
- Identifiers: 26-character ULIDs unless noted. Surrogate keys are preferred over composite primaries for consistency.
- All tenant-scoped rows include a `workspace_id` and enforce referential integrity back to `workspaces`.

## Enums
- `userrole`: `admin | user`
- `workspacerole`: `owner | member`

## Core Tables

### users
Stores people and service principals allowed to sign in.
- `user_id` (PK), `email`, `email_canonical`, `display_name`, `is_service_account`, `is_active`, `role` (enum), `last_login_at`, `failed_login_count`, `locked_until`, timestamps.
- Relationships: `user_credentials`, `user_identities`, `workspace_memberships`, `api_keys`.

### user_credentials
Holds password hashes for local authentication.
- `credential_id` (PK), `user_id` (FK to `users`), `password_hash`, `last_rotated_at`, timestamps.
- Unique constraint on `user_id` enforces at most one active password secret per user.

### user_identities
Normalized SSO identities.
- `identity_id` (PK), `user_id` (FK to `users`), `provider`, `subject`, `last_authenticated_at`, timestamps.
- Unique `(provider, subject)` ensures no duplicates.

### workspaces
Tenant boundary for all data.
- `workspace_id` (PK), `name`, `slug` (unique), `settings` (JSON), timestamps.

### workspace_memberships
Connects users to workspaces.
- `workspace_membership_id` (PK), `workspace_id` (FK), `user_id` (FK), `role` (enum), `is_default`, `permissions` (JSON), timestamps.
- Constraint: unique `(user_id, workspace_id)` enforces one membership per workspace.

### configurations
Versioned extraction instructions.
- `configuration_id` (PK), `workspace_id` (FK), `document_type`, `title`, `version`, `is_active`, `activated_at`, `payload` (JSON), timestamps.
- Unique `(workspace_id, document_type, version)` plus partial unique index on `(workspace_id, document_type)` where `is_active = 1`.

### documents
Uploaded source files.
- `document_id` (PK), `workspace_id` (FK), metadata (`original_filename`, `content_type`, `byte_size`, `sha256`, `stored_uri`, `attributes` JSON), retention fields (`expires_at`, `deleted_at`, `deleted_by_user_id`), `produced_by_job_id` (nullable job identifier), timestamps.

### api_keys
Hashed API keys bound to users or service accounts.
- `api_key_id` (PK), `user_id` (FK with cascade), `token_prefix` (unique), `token_hash` (unique), `label`, `expires_at`, `revoked_at`, `last_seen_at`, `last_seen_ip`, `last_seen_user_agent`, timestamps.
- Index: `api_keys_user_id_idx` for owner lookups; revoke keys via `revoked_at` without deleting history.

### jobs
Processing runs that turn documents into tables.
- `job_id` (PK), `workspace_id` (FK), `document_type`, `configuration_id` (FK), `status`, `created_by_user_id` (nullable FK to `users`), `input_document_id` (FK to `documents`), `metrics` (JSON), `logs` (JSON), timestamps.

### system_settings
Key/value store for global toggles.
- `key` (PK, e.g. `auth.force_sso`), `value` (JSONB), timestamps.

## Integrity Rules
- Every tenant-scoped table includes a `workspace_id` FK to enforce isolation.
- Jobs reference a single configuration version via `configuration_id` and cache the `document_type` for filtering convenience.
- Service code must set exactly one default membership per user; the uniqueness constraint prevents duplicates.
- Only one active configuration per `(workspace, document_type)` enforced via filtered unique index.
## Operational Notes
- Use deterministic ULIDs for IDs during seeding/tests to simplify fixtures.
- When adding new tenant-scoped tables, include both the FK to `workspaces` and supporting indexes on `(workspace_id, created_at)` for pagination.
- Metrics endpoints should source throughput and success rates from `jobs` lifecycle timestamps; avoid duplicating aggregates in separate tables until necessary.
- System settings keys should follow a dotted namespace (`auth.force_sso`). Values stored as JSONB for flexibility but read through typed config helpers.

## Next Steps
This schema refactor requires aligning ORM models, repositories, and API contracts. Refer to `agents/SCHEMA_REFACTOR_PLAN.md` for the implementation work package.
