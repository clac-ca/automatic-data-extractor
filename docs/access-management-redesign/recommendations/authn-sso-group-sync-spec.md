# AuthN, SSO, and Group Sync Spec

## Current Baseline

- ADE already supports OIDC SSO provider config and JIT user provisioning.
- Entra subject normalization (`tid:oid`) and email extraction exist.
- Current SSO model links user identity (`sso_identities`) but does not sync group objects/memberships.

Code references:

- `backend/src/ade_api/features/auth/sso_claims.py:47`
- `backend/src/ade_api/features/auth/sso_router.py:170`
- `backend/src/ade_db/models/sso.py:144`

## Target Objectives

1. Keep OIDC sign-in and JIT provisioning.
2. Add optional IdP group ingestion and membership synchronization.
3. Support both manual internal groups and provider-managed groups.
4. Keep dynamic memberships provider-managed in ADE first cut.

## Identity Source Strategy

### Users

- `source=internal` for ADE-created or invitation-created users.
- `source=idp` for users provisioned/managed by IdP sync.
- Stable correlation via `external_id`.

### Groups

- `source=internal` for ADE groups.
- `source=idp` for synced groups.
- Stable correlation via `external_id`.

## Sync Modes

## Mode 1: Login-time claims update (lightweight)

- Update basic user profile fields on successful login.
- Do not perform full group reconciliation here.

## Mode 2: Scheduled full sync (recommended first cut)

- Periodic pull from provider API (Graph/SCIM connector).
- Upsert groups by `external_id`.
- Upsert memberships for provider-managed groups.
- Mark deletions/removals in ADE to mirror provider state.

## Mode 3: Event-driven delta sync (future)

- Webhook/delta API support for near-real-time updates.

## Dynamic Group Rules

1. If group is `membership_mode=dynamic`, ADE membership write endpoints return `409`/`422` with read-only reason.
2. Dynamic memberships are updated by sync jobs only.
3. UI clearly labels dynamic groups as IdP-managed.

## SCIM Compatibility Requirements

1. Keep user fields compatible with SCIM core + enterprise extension.
2. Keep group schema compatible with SCIM group object model.
3. Reserve endpoint family for future SCIM server support (`/scim/v2/Users`, `/scim/v2/Groups`).

## Role Grant from Synced Groups

1. Synced groups can be assigned ADE roles at org/workspace scope.
2. Effective access recalculates when membership sync changes.
3. Audit events include provider and correlation IDs.

## Security and Governance

1. Sync connector credentials stored securely and rotated.
2. Sync job runs are idempotent and replay-safe.
3. Membership removals are processed promptly to avoid stale access.
4. Sync failures surface metrics and alerts.

## Failure Handling

1. Soft-fail on transient provider errors with retry/backoff.
2. Mark sync run status as degraded and alert if SLA exceeds threshold.
3. Never auto-promote privileges from partial/incomplete sync data.

