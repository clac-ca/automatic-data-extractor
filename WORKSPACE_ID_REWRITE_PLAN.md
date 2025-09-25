# Workspace ID Routing Plan (Greenfield Design)

## 1. Goal & Context
- **Objective**: Design workspace-aware routing that encodes the workspace identifier directly in REST URLs (e.g., `/workspaces/{workspace_id}/documents`) so the boundary is obvious to clients, logs, and generated SDKs.
- **Assumptions**: No production users exist yet, so we do not need compatibility layers for the legacy `X-Workspace-ID` header. We can implement the simplest correct approach from day one.
- **Desired outcome**: A minimal, coherent routing/story that is easy to explain, test, and extend as additional workspace-scoped features arrive.

## 2. Simplicity-First Design Principles
1. **Single source of truth** – Only accept the workspace identifier through the URL path; eliminate duplicate sources (headers, query params) to reduce drift.
2. **Consistent router structure** – Every workspace-scoped endpoint should live under `/workspaces/{workspace_id}` with predictable subpaths, so developers can infer routes without searching.
3. **Thin dependencies** – Resolve the `workspace_id` once in a shared dependency that loads the workspace model (or raises) and attaches it to `request.state` for downstream use. Avoid cascading helpers or decorators.
4. **Self-documenting APIs** – Ensure OpenAPI schemas, SDK generation, and documentation naturally surface the workspace context through path parameters.

## 3. Proposed Architecture
### 3.1 Router Composition
- Define a factory such as `workspace_scoped_router(subpath: str = "") -> APIRouter` that returns a router with `prefix=f"/workspaces/{{workspace_id}}{subpath}"` and tags indicating workspace scope.
- Organize modules (documents, jobs, configurations, etc.) so each exposes a router built via this helper. Routers only specify endpoints relative to their subpath.
- The FastAPI application registers each module router once. There is no legacy routing tree.

### 3.2 Workspace Resolution Dependency
- Implement a dependency `get_current_workspace(workspace_id: WorkspaceId) -> Workspace` that:
  1. Accepts the `workspace_id` `Path` parameter directly.
  2. Validates / fetches the workspace from persistence.
  3. Stores the resolved model on `request.state.current_workspace` and returns it for handler injection.
- Remove any references to `X-Workspace-ID`; the dependency is the only way to acquire workspace context.
- Authorization utilities simply require a resolved workspace object (already guaranteed by the dependency) and therefore remain straightforward.

### 3.3 Handler Patterns
- Endpoint signatures request the workspace explicitly: `async def list_documents(workspace: Workspace = Depends(get_current_workspace))`.
- Services continue to accept a `Workspace` domain object, keeping transport-layer concerns outside the core logic.
- URL construction helpers (background jobs, pagination) always include the workspace path segment using a single utility, e.g., `workspace_url(workspace_id, "/documents")`.

## 4. Delivery Steps
1. **Routing groundwork**
   - Create the router factory and migrate/author module routers using it.
   - Update `main.py` (or equivalent entrypoint) to include the rebuilt routers only under the workspace-prefixed structure.
2. **Dependency implementation**
   - Add `get_current_workspace` (and any small supporting types) in `backend/api/modules/workspaces/dependencies.py`.
   - Remove the old header-parsing utilities entirely.
3. **Endpoint adjustments**
   - Update every workspace-aware endpoint to depend on `get_current_workspace` and drop header expectations.
   - Ensure tests/fixtures call endpoints with URLs containing `/workspaces/{workspace_id}`.
4. **Validation & docs**
   - Refresh pytest coverage for routers, dependencies, and service integration.
   - Regenerate or verify OpenAPI docs to confirm the workspace path parameter appears everywhere.
   - Update README, API reference docs, CLI samples, and any SDK stubs to showcase the new URLs.

## 5. Keeping the Plan Simple
- **No transition code**: by skipping dual-header support, we avoid branches, warnings, and extra tests.
- **Minimal helpers**: one router factory + one dependency keeps the mental model compact.
- **Consistent naming**: use `workspace_id` uniformly in URLs, schemas, and code to prevent confusion.
- **Shared utilities**: centralize URL building so background tasks and pagination links naturally include the workspace segment.

## 6. Risks & Mitigations
- **Risk**: Forgetting to attach the dependency to a new route. → Mitigation: create a test (or lint) that asserts all workspace routers include the dependency, or expose a base router mixin that wires it automatically.
- **Risk**: Hard-coded URLs omit the workspace segment. → Mitigation: prefer the shared `workspace_url` helper and add tests covering pagination/link generation.
- **Risk**: Workspace lookup latency surfaces early. → Mitigation: keep the dependency straightforward so caching or prefetch strategies can be layered later if needed.

## 7. Open Questions
- Should we introduce slugs or keep opaque IDs? (Default: stick with IDs until product requests human-readable slugs.)
- Do any modules need workspace-agnostic routes (e.g., admin operations)? If so, document them explicitly to avoid mixing scopes.

