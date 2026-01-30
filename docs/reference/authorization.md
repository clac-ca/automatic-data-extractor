# Authorization Architecture

The Automatic Data Extractor (ADE) relies on a unified RBAC model where
principal → role assignments drive every permission decision. This document
summarises the building blocks, runtime flow, and public API so engineers and
operators can reason about access control without diving through the codebase.

## Core entities

- **Principals** represent subjects that can receive roles. Today every
  principal wraps a user record; the schema leaves room for future principal
  types without structural changes (`ade_api/models/user.py`).
- **Permissions** are Graph-style keys that include resource and action columns,
  allowing the API and UI to group capabilities predictably
  (`ade_api/models/rbac.py`).
- **Roles** bundle permissions at either global or workspace scope and enforce
  slug uniqueness within that scope while cascading permissions on delete
  (`ade_api/models/rbac.py`).
- **Role assignments** attach roles to principals at a scope. The database
  ensures scope consistency and cascades with principals, roles, and workspaces
  so authorisation data stays clean (`ade_api/models/rbac.py`).

## Permission registry and seeds

Permissions and default roles live in `ade_api/core/rbac/registry.py`. Each
entry defines its key, scope, label, description, and implied defaults. The
system role catalog seeds administrator and workspace owner/member experiences
aligned with the registry, so permissions are consistent across API, UI, and
migrations.

## Service layer and decision flow

The RBAC service (`ade_api/features/rbac/service.py`) normalises permission
keys, expands implication rules, and exposes helpers for role CRUD and
assignment upserts. Permission checks flow through `ade_api/core/http`
dependencies, which compute effective permissions for the current principal and
scope before allowing a request to proceed. Workspace profiles reuse the same
assignment data so global administrators inherit owner capabilities when
reviewing a workspace.

## FastAPI security dependencies

Shared dependencies wrap authentication and permission checks so routers declare
their requirements with `Security(...)`. Denials surface the missing permission,
scope type, and scope identifier in a structured JSON error body to simplify
debugging and audits (`ade_api/core/http/dependencies.py`). A `require_csrf`
placeholder is present on mutating routes but currently no-ops; it remains to
ease future CSRF enforcement.

## Public API

All RBAC administration lives under `/api/v1`:

- Permission catalog: `GET /permissions`.
- Role catalog and CRUD (global or workspace-scoped via query params):
  `GET/POST /roles`, `GET/PATCH/DELETE /roles/{roleId}`.
- Global role assignments (admin listing/upserts): `GET /roleassignments`.
- Global roles for a specific user: `GET /users/{userId}/roles`,
  `PUT/DELETE /users/{userId}/roles/{roleId}`.
- Workspace membership + role bindings:
  `/workspaces/{workspaceId}/members` (list/create/update/delete).
- Effective permission introspection via `/me/permissions` and
  `/me/permissions/check`.

## Operational notes

- Tests seed principals, workspace roles, and assignments so API and service
  coverage exercise the same Graph-style keys the registry declares
  (`apps/ade-api/conftest.py`).
- The baseline migration (`0001_initial_schema`) mirrors this structure and adds
  indexes/constraints for scope lookups and system role uniqueness in Postgres
  (`apps/ade-api/src/ade_api/migrations/versions/0001_initial_schema.py`).

Keep this reference updated whenever the registry, service layer, or router
contracts evolve so onboarding engineers can rely on the docs instead of reading
through the full diff.
