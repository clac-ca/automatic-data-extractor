# Workspace Permission Scopes

This project enforces workspace-level permissions through declarative FastAPI
dependencies. Each scope follows the `workspace:<resource>:<action>` pattern so
routers can communicate their requirements directly when defining handlers.

## Scope Catalogue

Workspace scopes live alongside the workspace service in
`app/features/workspaces/service.py` via the `WorkspaceScope` `StrEnum`. The
module also provides a helper for normalising scope collections so services and
dependencies reason about the same canonical values. Routes pass the enum
constants directly into FastAPI's `Security` dependency, keeping required scopes
obvious at the point of declaration.【F:app/features/workspaces/service.py†L20-L98】【F:app/features/documents/router.py†L27-L109】

## Default Role Grants

Role-specific defaults sit next to the enum in `ROLE_SCOPE_DEFAULTS`. Members
receive read/write access for day-to-day document processing, while owners add
member and settings management capabilities. Service logic consumes these
defaults, normalises them with any custom grants stored on memberships, and
returns a sorted list so responses always expose a canonical view of the
permissions. Future role types can extend the defaults by appending new scope
values without touching the dependency graph.【F:app/features/workspaces/service.py†L20-L118】【F:app/features/workspaces/service.py†L330-L396】

## Enforcement Pattern

Routes enforce permissions through the `require_workspace_access` dependency.
Handlers specify their required scopes directly in the router definition using
FastAPI's `Security` helper. During dependency resolution we look up the
caller’s workspace profile, compare the normalised grants to the requested
scopes, and return the profile when the requirements are met. Endpoint logic
then reuses the validated `WorkspaceProfile.workspace_id` when invoking
services so every handler works with the same canonical identifier FastAPI
resolved. Global
administrators receive an owner-level profile from the workspace service, so
they naturally satisfy every declared scope without a separate bypass.【F:app/features/workspaces/dependencies.py†L46-L79】【F:app/features/workspaces/service.py†L44-L129】【F:app/features/jobs/router.py†L54-L174】

## Testing & Fixtures

Fixtures and feature tests import the same enum to grant permissions or assert
on returned payloads. This keeps the test data aligned with the application
logic and guards against typos in raw scope strings.【F:app/features/jobs/tests/test_router.py†L64-L148】【F:app/features/workspaces/tests/test_router.py†L81-L316】【F:conftest.py†L29-L241】

