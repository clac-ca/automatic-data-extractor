# Work Package: Simplify FastAPI Service Dependencies

## Snapshot
- **Goal:** Remove over-engineered service context patterns so feature routers use small, composable dependencies per FastAPI guidance.
- **Owner:** Backend platform team (agents execute incremental milestones).
- **Time horizon:** Two to three focused PRs; each should remain deployable and keep behavioural parity.
- **Reference:** `agents/fastapi-best-practices.md`

---

## Context & Motivation
Our backend already follows the feature-first layout recommended in the playbook, but the service layer still leans on a custom
`ServiceContext` factory that injects request state, user data, permissions, settings, and a task queue into every service instance.
Routers then call a generic `access_control()` helper that wraps the same service dependency to perform permission checks before
handing it back to the endpoint. This layering adds indirection on every request, hides the actual inputs each service needs, and
encourages state to be passed implicitly via `request.state`. The FastAPI best-practice guide encourages small, explicit dependencies
that can be chained and cached, avoiding unnecessary abstraction and favouring predictable, testable units.【F:agents/fastapi-best-practices.md†L314-L406】

This work package trims the custom service machinery, making dependencies simpler to read and mocking easier during tests.

---

## Target Areas & Plans

### 1. Collapse `ServiceContext` / `BaseService` abstractions
#### Why it deviates
- `app/core/service.py` constructs a `ServiceContext` with request, user, workspace, permissions, and a task queue for *every* service,
  even when most services only require a session and settings. The context then re-reads `request.state` whenever attributes are missing
  and exposes helpers like `require_workspace_id()` that hide required arguments.【F:app/core/service.py†L1-L160】
- This mirrors the “everything bag” anti-pattern called out in the playbook: we are effectively injecting the whole application state
  instead of small, cached dependencies for each responsibility.【F:agents/fastapi-best-practices.md†L314-L406】

#### Simplification approach
Expose explicit dependencies per service (e.g. session, settings, current user) and initialise services with concrete parameters. Drop
`ServiceContext` and make the service constructors accept the exact objects they operate on. This keeps dependency graphs discoverable
and lets FastAPI cache shared dependencies automatically.

#### Refactor steps
1. Replace `service_dependency()` with feature-local factory functions (e.g. `async def get_workspaces_service(session=Depends(get_session), settings=Depends(get_settings))`).
2. Update service classes (auth, workspaces, jobs, etc.) to accept constructor parameters instead of a `ServiceContext` and remove
   `BaseService` inheritance.
3. Inline helpers like `BaseService.current_user` by passing `current_user` into the method that needs it, or expose a thin dependency
   that returns the typed user model.
4. Delete `app/core/service.py` after all consumers move to explicit dependencies; adjust imports accordingly.
5. Refresh tests to inject the simpler constructor arguments directly.

### 2. Decouple authorisation from service construction
#### Why it deviates
- `access_control()` wraps a service dependency, runs permission checks on the service’s `current_user` / `permissions`, and then returns
  the same service object to the router. This couples authorisation with object lifetime and assumes permission data lives on the
  service via request state. It also hides which dependencies the route truly needs because the `Depends` call only surfaces the
  service type.【F:app/features/auth/security.py†L183-L237】【F:app/features/workspaces/router.py†L33-L198】

#### Simplification approach
Use small, chainable dependencies: resolve the current user/workspace/permissions up front, perform permission checks in their own
dependencies, and pass both the authorised principal and the service into the endpoint separately. This mirrors the playbook’s guidance
on composing reusable dependencies and lets FastAPI cache the authorised user while instantiating the service independently.【F:agents/fastapi-best-practices.md†L314-L406】

#### Refactor steps
1. Create dedicated dependencies such as `require_permissions(required: set[str])` that consume `current_permissions` without touching
   service factories.
2. Update routers (workspaces, jobs, documents, etc.) to inject `(principal, workspace_context, service)` explicitly instead of relying on
   `access_control()` to return a service.
3. Remove `access_control()` once all routes use the new helpers, keeping only cryptographic utilities inside `auth/security.py`.
4. Adjust tests and fixtures to call the new permission dependency directly.

### 3. Stop mutating `request.state` for workspace context
#### Why it deviates
- `bind_workspace_context()` writes `current_workspace` and `current_permissions` into `request.state` so downstream services can pull
  them implicitly via `BaseService`. This is only needed because services expect the global context; it makes dependencies order-sensitive
  and hides the actual parameters passed to service methods.【F:app/features/workspaces/dependencies.py†L1-L75】【F:app/core/service.py†L58-L99】

#### Simplification approach
Return the `WorkspaceContext` from the dependency and pass it directly to services or endpoint functions that need it. Services that act on
a workspace should accept the context (or just the workspace ID) as an argument rather than reading from global state.

#### Refactor steps
1. Update service methods (e.g. `JobsService.submit_job`, `WorkspacesService.update_workspace`) to accept a `workspace_context` parameter and
   rely on the router to pass it in.
2. Remove the `request.state` writes inside `bind_workspace_context()` once services no longer expect them.
3. Replace `BaseService.require_workspace_id()` calls with direct use of the workspace context passed into each method.
4. Simplify tests by providing explicit workspace fixtures without needing to simulate request state.

---

## Deliverables
- Removal of `app/core/service.py` and migration to explicit dependency factories per feature.
- Replacement of `access_control()` with small, composable permission dependencies.
- Workspace-aware services that receive context explicitly, eliminating hidden request state coupling.
- Updated tests and fixtures reflecting the simplified dependency graph.

---

## Risks & Mitigations
- **Risk:** Service constructors may need extensive signature changes across the codebase. *Mitigation:* Tackle one feature per PR and
  provide temporary adapter functions if required.
- **Risk:** Permission checks could regress if refactored hastily. *Mitigation:* Add focused tests for permission helpers during the first
  refactor and reuse them across features.
- **Risk:** Some background workers or CLI commands might still depend on `BaseService`. *Mitigation:* Audit non-API entry points early and
  introduce explicit dependency providers there as well.

---

## Exit Criteria
- Services are instantiated through explicit constructor arguments without `ServiceContext`.
- Permission checks run through declarative dependencies that return clear types (user, workspace, permissions).
- No runtime code writes workspace data into `request.state`; endpoints pass context explicitly.
- Test suites cover the new dependency helpers and continue to pass (`pytest`, `mypy app`).

---

## Status – 2025-02-14
- Added `app/api/settings.py` with a request-scoped `AppSettings` dependency so feature services receive the application’s live settings instead of loading stale environment values.
- Updated auth, documents, health, and jobs dependencies to consume the new helper; document upload size enforcement now honours `override_app_settings` in tests and runtime checks.
- `pytest` and `ruff check` succeed after the dependency updates, unblocking the broader service-context removal work.
- Inlined FastAPI dependencies across features, dropping the `AppSettings` alias and `Annotated` wrappers so routers clearly express the dependencies they need.
- Replaced feature-level `get_*_service` dependency factories with inline `Depends(get_session)` / `Depends(get_app_settings)` parameters so routers and dependencies instantiate services directly without intermediary helpers.
- Removed the `WorkspaceAccess` wrapper and permission dependency closures so routers inject workspace context and the current user directly, checking permissions inline via a small helper.
- Standardised workspace-scoped routers to inline consistent dependency order and local workspace identifiers, keeping service calls and permission enforcement uniform across features.
- Updated workspace services to accept plain workspace identifiers so every feature now instantiates services with the same `workspace_id` pattern before invoking business logic.
- Normalised workspace-scoped routers to annotate identifier path parameters with inline `Path` metadata so each feature exposes consistent FastAPI signatures.
- Introduced a header-aware `resolve_workspace_identifier` dependency so workspace endpoints no longer double-check path parameters and can fall back to a member's default workspace when no identifier is supplied.
- Updated the workspace identifier resolver to lean on FastAPI's parameter injection instead of interrogating the `Request`, keeping routing logic declarative while supporting both path segments and the `X-Workspace-ID` header consistently.
- Prioritised explicit overrides by teaching the workspace identifier dependency to prefer headers and query parameters while normalising router call sites with `WorkspaceContext` convenience accessors, keeping workspace-aware features uniform.
- Simplified workspace identifier resolution to rely solely on the route path parameter, removing header and query overrides so workspace-scoped dependencies match FastAPI's conventional patterns.
- Removed the `WorkspaceContext` wrapper so workspace dependencies now return plain `WorkspaceProfile` data, keeping routers and services aligned with FastAPI's direct dependency style.
- Added explicit `workspace_id` path parameters to every workspace-scoped route so identifiers are defined by the router itself while membership dependencies stay focused on permission checks.
- Rebuilt workspace permission enforcement around FastAPI's `Security` scopes with a `require_workspace_access` dependency so routers declare permissions idiomatically without custom closures.
- Centralised workspace scope constants, updated routers and tests to consume them, and documented the permission dependency so FastAPI handlers enforce scopes consistently across the codebase.
- Simplified the workspace permission dependency to rely on the resolved profile's scopes, removing the redundant administrator bypass and extra user injection.
- Normalised workspace scope handling with typed helpers so dependencies and
  services share the same expansion, validation, and serialization logic while
  routers declare scopes with the shared enum.
- Collapsed the dedicated workspace scope module into the workspace service so
  FastAPI routes, dependencies, and tests reference a single, conventional
  source for scope constants alongside the logic that consumes them.
- Simplified workspace scopes to use explicit grants only, dropping implied
  scope expansion so permission checks mirror FastAPI's direct `Security`
  comparisons and keep the door open for future custom role definitions without
  hidden behaviour.
- Updated workspace-scoped routers to depend solely on the resolved
  `WorkspaceProfile`, reusing its validated identifier for service calls so
  handlers stay aligned with FastAPI's dependency-driven parameter flow across
  features.
- Dropped the `workspace_scoped_router` helper so documents, configurations,
  and jobs routers declare their FastAPI prefixes directly, matching the
  framework's conventional router setup.
