# Workspace Permission Scopes

ADE models workspace access using the Graph-style permission keys defined in
`app/features/roles/registry.py`. Workspace routes now lean on the shared
`require_workspace` security dependency so the required capabilities are visible
in OpenAPI and enforced through the unified `authorize` service.【F:app/features/roles/registry.py†L25-L120】【F:app/api/security.py†L52-L118】【F:app/features/workspaces/router.py†L82-L341】

## Default grants

`WorkspacesService` unions permissions from every role assignment, expanding
implication rules so `.ReadWrite` grants satisfy the paired `.Read` checks and
ensuring any workspace key implies the baseline `Workspace.Read`. Owners receive
the full system role set (including role and member administration), while
members default to the day-to-day document and configuration scopes.【F:app/features/workspaces/service.py†L33-L357】

## Enforcement flow

The `require_workspace` dependency resolves the workspace scope from the
incoming request, binds the authenticated principal, and calls `authorize`
directly. Global administrators reuse the same path: `WorkspacesService`
provides an owner-level profile so they satisfy every workspace-scoped
requirement without bespoke bypass logic.【F:app/api/security.py†L52-L118】【F:app/features/workspaces/service.py†L68-L216】

## Tests and fixtures

Feature tests and fixtures assert against the same Graph-style strings to ensure
the runtime and tests stay aligned. The seeded fixtures create owner and member
assignments without bespoke overrides, and the router tests exercise both
success and failure paths for key-protected routes (job submission, membership
management, workspace deletion).【F:conftest.py†L110-L247】【F:app/features/workspaces/tests/test_router.py†L44-L707】【F:app/features/jobs/tests/test_router.py†L16-L150】
