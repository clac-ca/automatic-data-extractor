# Workspace Permission Scopes

ADE models workspace access using the Graph-style permission keys defined in
`app/features/roles/registry.py`. Workspace routes reference these keys directly
via FastAPI's `Security` dependency so the required capabilities stay visible at
the point of declaration.【F:app/features/roles/registry.py†L25-L121】【F:app/features/workspaces/router.py†L83-L341】

## Default grants

`WorkspacesService` now unions permissions from every role assigned to a
membership, expanding implication rules so `.ReadWrite` grants satisfy the
paired `.Read` checks and ensuring any workspace key implies the baseline
`Workspace.Read`. Owners receive the full system role set (including role and
member administration), while members default to the day-to-day document and
configuration scopes.【F:app/features/workspaces/service.py†L26-L357】

## Enforcement flow

The `require_workspace_access` dependency resolves the caller's
`WorkspaceProfile`, compares the requested scopes to the computed permission
list, and raises `403` when any required key is missing. Global administrators
reuse the same path: `WorkspacesService` issues an owner-level profile so they
satisfy every workspace-scoped requirement without bespoke bypass logic.【F:app/features/workspaces/dependencies.py†L35-L78】【F:app/features/workspaces/service.py†L79-L216】

## Tests and fixtures

Feature tests and fixtures assert against the same Graph-style strings to ensure
the runtime and tests stay aligned. The seeded fixtures create owner and member
records without bespoke overrides, and the router tests exercise both success
and failure paths for key-protected routes (job submission, membership
management, workspace deletion).【F:conftest.py†L90-L228】【F:app/features/workspaces/tests/test_router.py†L42-L704】【F:app/features/jobs/tests/test_router.py†L14-L148】
