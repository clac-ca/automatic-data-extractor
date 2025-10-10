# Authorization Architecture

The Automatic Data Extractor (ADE) now relies on a unified RBAC model where
principal → role assignments drive every permission decision. This document
summarises the building blocks, runtime flow, and public API so engineers and
operators can reason about access control without diving through the codebase.

## Core entities

- **Principals** represent subjects that can receive roles. Today every
  principal wraps a user record and enforces the link through a check constraint
  so future principal types (service accounts, groups) can be added without
  schema changes.【F:ade/features/roles/models.py†L16-L61】
- **Permissions** are Graph-style keys that include resource and action columns,
  allowing the API and UI to group capabilities predictably.【F:ade/features/roles/models.py†L63-L85】
- **Roles** bundle permissions at either global or workspace scope and enforce
  slug uniqueness within that scope while cascading assignments and permissions
  on delete.【F:ade/features/roles/models.py†L88-L142】
- **Role assignments** attach roles to principals at a scope. The database
  ensures scope consistency and cascades with principals, roles, and workspaces
  so authorisation data stays clean.【F:ade/features/roles/models.py†L145-L189】

## Permission registry and seeds

Permissions and default roles live in a declarative registry. Each entry defines
its key, scope, label, description, and implied defaults, while the system role
catalog seeds administrator and workspace owner/member experiences aligned with
Microsoft Graph conventions.【F:ade/features/roles/registry.py†L1-L132】【F:ade/features/roles/registry.py†L134-L211】

## Service layer and decision flow

The role service normalises permission keys, expands implication rules (for
example, `.ReadWrite` implies `.Read`), and exposes helpers for CRUD operations
and assignment upserts.【F:ade/features/roles/service.py†L1-L213】【F:ade/features/roles/service.py†L215-L366】

Route-level guards ultimately call the principal-oriented `authorize` facade,
which delegates to the service functions to compute granted permissions for the
requested scope.【F:ade/features/roles/authorization.py†L1-L52】 Workspace
profiles reuse the same assignment data so global administrators inherit owner
capabilities when reviewing a workspace.【F:ade/features/workspaces/service.py†L33-L142】

## FastAPI security dependencies

Shared dependencies wrap authentication, CSRF enforcement, and permission checks
so routers declare their requirements with `Security(...)`. Denials surface the
missing permission, scope type, and scope identifier in a structured JSON error
body to simplify debugging and audits.【F:ade/api/security.py†L1-L118】

## Public API

All RBAC administration lives under `/api/v1`:

- Global role catalog and CRUD: `GET/POST /roles?scope=global`, `GET/PATCH/DELETE
  /roles/{role_id}`.【F:ade/features/roles/router.py†L76-L335】
- Workspace role catalog and mutations: `GET/POST /workspaces/{workspace_id}/roles`
  and the workspace-aware patch/delete fallbacks in the roles router.【F:ade/features/roles/router.py†L336-L398】
- Global role assignments: list/create/delete via
  `/role-assignments` endpoints.【F:ade/features/roles/router.py†L492-L649】
- Workspace role assignments: list/create/delete via
  `/workspaces/{workspace_id}/role-assignments` endpoints guarded by workspace
  permissions.【F:ade/features/roles/router.py†L651-L760】
- Permission catalog and effective permission introspection via
  `/permissions`, `/me/permissions`, and `/me/permissions/check` (not shown
  above) reuse the same dependencies for parity.【F:ade/features/roles/router.py†L200-L291】

## Operational notes

- The CLI automatically synchronises the permission registry before creating a
  user and assigns the requested global role by slug (`admin` →
  `global-administrator`, `user` → `global-user`).【F:ade/cli/commands/users.py†L1-L122】
- Tests seed principals, workspace roles, and assignments so API and service
  coverage exercise the same Graph-style keys the registry declares.【F:conftest.py†L110-L247】
- The baseline migration (`0001_initial_schema`) mirrors this structure and adds
  indexes/constraints for scope lookups and system role uniqueness in SQLite and
  Postgres.【F:ade/alembic/versions/0001_initial_schema.py†L1-L310】

Keep this reference updated whenever the registry, service layer, or router
contracts evolve so onboarding engineers can rely on the docs instead of reading
through the full diff.
