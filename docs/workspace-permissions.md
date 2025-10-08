# Workspace Permission Scopes

ADE models workspace access using the Graph-style permission keys defined in
`app/features/roles/registry.py`. Workspace routes reference these keys directly
via FastAPI's `Security` dependency so the required capabilities stay visible at
the point of declaration.【F:app/features/roles/registry.py†L25-L121】【F:app/features/workspaces/router.py†L83-L341】

## Default grants

`WorkspacesService` derives each member's permission list from
`ROLE_PERMISSION_DEFAULTS`, which maps the built-in `WorkspaceRole` enum to the
Graph keys exposed through API responses. Owners inherit the full workspace set
(including `Workspace.Delete`), while members receive the day-to-day read/write
permissions needed for document processing.【F:app/features/workspaces/service.py†L26-L153】【F:app/features/workspaces/service.py†L329-L357】

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
