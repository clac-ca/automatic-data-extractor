> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

 * [x] Baseline current auth/roles/documents call timings and DB queries for the documents screen (session, workspaces, safe-mode, documents). → Action: run `source .venv/bin/activate`, start the backend (`ade start` or equivalent), open a clean tab, load the documents screen once, and paste the console log into `.workpackages/db-perf-documents/logs/uploads/ade-documents-screen-post-caching.log` for comparison. — captured post-caching baseline in `logs/uploads/ade-documents-screen-post-caching.log` (bootstrap + documents only).
* [x] Cache/short-circuit roles registry sync and global role slug lookup so they do not run per request.
* [x] Make global role assignment + principal/permission resolution idempotent within a request (early exit when already assigned, reuse cached principal/permissions).
* [x] Add a backend bootstrap path or shared cache to avoid multiple auth/roles round-trips for one screen; update OpenAPI types and frontend usage.
* [x] Optimize documents list DB path (including last_run join) and add regression safeguards/metrics for latency.
* [x] Deep-dive `logs/ade-startup.log` and summarize perf findings in Section 6 — startup registry sync ~2s; no other heavy work observed.
* [x] Deep-dive `logs/ade-initial-setup.log` and summarize perf findings in Section 6 — startup build + migration; roles registry sync ~3.4s; session 3.3s; workspaces 1.8s with repeated role assignment.
* [x] Deep-dive `logs/ade-load-workspaces-page.log` and summarize perf findings in Section 6 — registry sync ~2s; parallel session/workspaces calls both redo role assignment; 1.9s+ latency.
* [x] Deep-dive `logs/ade-load-workspace-settings.log` and summarize perf findings in Section 6 — registry sync ~2.1s; safe-mode call incurs role assignment (~1.3s) even auth disabled.
* [x] Deep-dive `logs/ade-load-workspace-settings-members-tab.log` and summarize perf findings in Section 6 — registry sync ~2s; members/roles requests run in parallel with repeated assign_global; ~3.5–5.5s durations ending 422.
* [x] Deep-dive `logs/ade-load-workspace-settings-roles-tab.log` and summarize perf findings in Section 6 — registry sync ~2.1s; multiple parallel calls (permissions, workspace roles) redo assign_global; ~2.6–4.3s durations ending 422.
* [x] Deep-dive `logs/ade-creating-workspace.log` and summarize perf findings in Section 6 — registry sync ~2.1s; workspace creation POST ~4.6s with repeated assign_global; follow-up GETs (workspaces, safe-mode) also redo role work (~3.2s).
* [x] Deep-dive `logs/ade-creating-config-from-template.log` and summarize perf findings in Section 6 — registry sync ~2.1s; config list ~3.0s, safe-mode ~1.35s, config create ~2.7s, second list ~2.5s; all redo assign_global.
* [x] Deep-dive `logs/ade-load-config-builder-page.log` and summarize perf findings in Section 6 — registry sync ~2.1s; config list ~3.1s; safe-mode ~1.35s; all repeat assign_global.
* [x] Deep-dive `logs/ade-load-config-builder-editor.log` and summarize perf findings in Section 6 — registry sync ~2.1s; safe-mode ~1.36s; config files list ~3.17s; file read ~2.39s; every call redoes assign_global.
* [x] Deep-dive `logs/ade-start-config-builder-validation.log` and summarize perf findings in Section 6 — registry sync ~2s; validation POST builds env/run in ~14.9s; repeated assign_global; pool warning for unclosed aioodbc connection.
* [x] Deep-dive `logs/ade-start-config-builder-test-run.log` and summarize perf findings in Section 6 — registry sync ~2s; documents list 4.1s; sheets 3.6s; run POST ~12.2s; repeated assign_global everywhere; safe-mode ~1.5s; run outputs/summary/logfile ~1.3–1.5s each with role overhead.
* [x] Deep-dive `logs/ade-upload-document.log` and summarize perf findings in Section 6 — safe-mode ~1.35s; document POST ~4.2s; documents GET ~3.9s; all redo assign_global.
* [x] Deep-dive `logs/ade-upload-multiple-documents.log` and summarize perf findings in Section 6 — each document POST ~3.7–4.2s with repeated role work; safe-mode ~1.83s; final documents GET ~3.6s.
* [x] Deep-dive `logs/ade-filter-documents-by-status.log` and summarize perf findings in Section 6 — log only covers startup + `/system/safe-mode`; noted role overhead.
* [x] Deep-dive `logs/ade-filter-by-recently-run.log` and summarize perf findings in Section 6 — registry sync ~2.1s; documents list (sorted by last_run) ~4.37s; safe-mode ~1.4s; repeated assign_global.
* [x] Code review `features/auth/service.py` (dev identity/assign_global/sync_permission_registry) for caching and idempotency options.
* [x] Code review `features/roles/service.py` (registry sync, get_by_slug, assign_role/assign_global) for per-request overhead and caching hooks.
* [x] Code review `features/documents/service.py` (list + last_run attach) to confirm query shape and potential optimizations/indexes.
* [x] Code review request-level caching options (dependency injection/middleware) to share identity/permissions across calls in one session.
* [x] Sketch bootstrap endpoint/server-side cache shape and update workpackage design accordingly.

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] Baseline timings — refs/notes`

---

# DB performance optimizations for documents screen bootstrap

## 1. Objective

**Goal:**
Reduce redundant DB work in the auth/roles/documents flow so the documents screen loads with minimal queries and sub-500ms backend latency per endpoint under normal dev data volumes.

You will:

* Map the current query path for session/workspaces/safe-mode/documents and identify redundant role/auth work.
* Add caching/idempotent guards around role registry sync, global role assignment, and principal/permission resolution.
* Provide an efficient bootstrap data path (or shared request/session cache) the frontend can reuse instead of issuing multiple parallel calls.

The result should:

* Eliminate repeated registry sync/role assignment queries for the same user per request chain.
* Provide observable latency drops for the documents screen (single bootstrap call or reused session data) with tests/metrics protecting the new behavior.

---

## 2. Context (What you are starting from)

Current logs show a documents screen load triggers multiple API calls (`/auth/session`, `/workspaces`, `/system/safe-mode`, `/workspaces/{id}/documents`) and each call re-runs `roles.registry.sync`, `roles.global.get_by_slug`, `roles.assignments.assign_global` (already exists), and `auth.dev_identity.ensure`. The documents list query itself is modest (~1.4s including last_run join) but overall latency is dominated by repeated auth/roles DB work (~5–6s end-to-end). Frontend issues parallel calls and does not reuse session bootstrap data.

Examples of what to capture here (replace with actual content):

* Existing structure: FastAPI app at `apps/ade-api/src/ade_api/` with features modules (`auth`, `roles`, `users`, `system_settings`, `workspaces`, `documents`).
* Current behavior / expectations: Dev identity auto-provisions and assigns `global-administrator` on every request; roles registry sync runs eagerly per request.
* Known issues / pain points: Repeated registry sync and global assignment queries; no per-request caching of principal/permissions; frontend fan-out multiplies the cost.
* Hard constraints (APIs, platforms, consumers): Must preserve permission semantics and dev identity convenience; avoid breaking existing OpenAPI consumers; keep behavior predictable in multi-tenant workspaces.

---

## 3. Target architecture / structure (ideal)

Auth/roles bootstrap work should be cached: registry sync happens once (startup or TTL/etags), global role slug lookup cached, and `assign_global` becomes a no-op when already assigned (using cached principal/permissions). A single bootstrap payload (or server-side request cache) provides user, permissions, safe-mode, and workspaces so subsequent calls skip redundant DB hits. Documents list reuses cached identity/permissions and performs a single optimized query (including last_run) with proper pagination and indexes.

```text
automatic-data-extractor/
  apps/ade-api/
    src/ade_api/features/
      auth/                 # request identity + caching hook
      roles/                # registry cache, idempotent assignments, permission cache
      system_settings/      # safe-mode lookup reused via bootstrap
      workspaces/           # workspace listing using cached principal/permissions
      documents/            # documents list + last_run retrieval using optimized query
    tests/
      features/
        auth/
        roles/
        documents/
        workspaces/
        system_settings/
    scripts/
      perf/                 # optional benchmarking/profiling helpers
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* Reduce per-request DB load by caching idempotent lookups (registry, global role slug, principal/permissions).
* Keep behavior transparent and testable with clear cache invalidation/TTL rules.
* Enable frontend to fetch/refresh bootstrap data once and reuse it to avoid redundant server work.

### 4.2 Key components / modules

* `roles.registry` — maintain cached permissions/roles; refresh via startup hook or TTL; expose cheap `get_by_slug`.
* `roles.assignments` — add `assign_if_missing`/idempotent path using cached principal lookup; avoid duplicate DB writes.
* `auth.dev_identity` / request context — cache user/principal/permissions per request or via bootstrap payload; expose to downstream dependencies.
* `documents.service` — ensure list + last_run query is optimized and uses cached identity/permissions; adjust ordering/pagination as needed.
* `bootstrap endpoint/cache` — return session + permissions + safe-mode + workspace membership in one call, or server-side cache used by existing routes.

### 4.3 Key flows / pipelines

* Bootstrap flow: establish identity → fetch cached registry → ensure global admin assignment (early exit) → fetch permissions → serve bootstrap payload (session/workspaces/safe-mode) without repeating DB hits per route.
* Documents list flow: reuse cached identity/permissions → run single documents query (with last_run join/subquery) → return paginated results without triggering registry sync or role assignment.

### 4.4 Open questions / decisions

* What cache invalidation/TTL strategy is acceptable for roles registry and slug lookups (startup-only vs. timed refresh vs. versioned rows)?
* Should bootstrap be a new endpoint (e.g., `/api/v1/bootstrap`) or implemented as server-side request caching leveraged by existing endpoints?
* How to gate dev-only identity caching to avoid surprises in production auth (feature flag or environment toggle)?

> **Agent instruction:**
> If you answer a question or make a design decision, replace the placeholder with the final decision and (optionally) a brief rationale.

---

## 5. Implementation & notes for agents

* Keep caches thread-safe for async FastAPI; prefer in-memory per-process with clear TTL and fallbacks.
* Add unit/integration coverage for caching and idempotent assignment; include regression timing assertions where feasible.
* If adding/changing endpoints, update OpenAPI and regenerate frontend types with `ade openapi-types`.
* Validate with `ade test` (and `ade ci` if touching multiple layers) before merging; capture perf deltas (before/after logs or simple benchmarks).
* Maintain existing permission semantics and dev identity ergonomics; ensure prod auth remains correct when dev identity is disabled.
* **Baseline rerun captured (2025-11-28):** `.workpackages/db-perf-documents/logs/uploads/ade-documents-screen-post-caching.log` — `/api/v1/bootstrap` ~3.4s plus documents GET ~1.76s with cached principal/roles and no extra safe-mode/workspaces calls. Continue to aim for <500ms per endpoint by profiling remaining hotspots.

---

## 6. Log deep-dive notes (fill as you analyze each file)

- `logs/ade-startup.log` — Startup includes roles registry sync (~2s). Auth disabled but registry sync still runs; no other notable startup work.
- `logs/ade-initial-setup.log` — Includes frontend build (2.1s) then DB migration (0001). Roles registry sync takes ~3.4s at startup. First `/api/v1/auth/session` creates dev identity principal and global admin assignment; call takes ~3.3s. Immediately after, `/api/v1/workspaces` redoes `roles.global.get_by_slug` + `assign_global` (already_exists) and permissions fetch; duration ~1.8s. Shows repeated role work even within same session; registry sync only once at startup.
- `logs/ade-load-workspaces-page.log` — Startup roles registry sync ~2s. Frontend fires `/api/v1/workspaces` and `/api/v1/auth/session` in parallel; both execute `roles.global.get_by_slug` + `assign_global` (already_exists) and permissions lookups. Workspaces call ~1.9s, session ~2.8s. Shows duplicated role work across concurrent requests.
- `logs/ade-load-workspace-settings.log` — Startup roles registry sync ~2.1s. Single `/api/v1/system/safe-mode` triggers dev identity and `assign_global` (already_exists) despite auth disabled; call takes ~1.3s.
- `logs/ade-load-workspace-settings-members-tab.log` — Startup roles registry sync ~2s. Three parallel requests (users list, workspace members, workspace roles) all trigger dev identity and `assign_global` (already_exists) repeatedly. `/api/v1/users` takes ~4.3s; `/workspaces/{id}/members` and `/roles` take 3.5–5.5s and return 422. Heavy duplicated role lookups dominate latency even before the 422 failure.
- `logs/ade-load-workspace-settings-roles-tab.log` — Startup roles registry sync ~2.1s. Multiple parallel requests (`/permissions?scope=global`, `/workspaces/{id}/roles`) each execute `roles.global.get_by_slug` + `assign_global` (already_exists) and permission fetches. Both endpoints return 422 and take ~2.6–4.3s. Heavy duplicated role work even when auth disabled.
- `logs/ade-creating-workspace.log` — Startup roles registry sync ~2.1s. Workspace creation flow: `/api/v1/users` takes ~3.0s with role assignment and permission fetch. `POST /api/v1/workspaces` takes ~4.6s; includes global role assignment (already_exists) plus workspace role assignment sync for new workspace. After creation, multiple parallel GETs (`/workspaces`, `/system/safe-mode`, etc.) re-trigger `assign_global` and permissions; safe-mode call alone ~3.2s. Heavy repeated role work even when auth disabled.
- `logs/ade-creating-config-from-template.log` — Startup roles registry sync ~2.1s. First `/configurations` GET takes ~3.1s with dev identity + `assign_global` (already_exists). Safe-mode call ~1.35s also redoes role assignment. Config creation POST (~2.7s) again re-runs `assign_global` before materializing template. Follow-up config list GET (~2.5s) also repeats the role path. Pattern: every call redoes global role lookup/assign despite auth disabled.
- `logs/ade-load-config-builder-page.log` — Startup roles registry sync ~2.1s. `/configurations` GET ~3.1s with dev identity + `assign_global` (already_exists). Safe-mode call ~1.35s also redoes role assignment. No additional config actions captured.
- `logs/ade-load-config-builder-editor.log` — Startup roles registry sync ~2.1s. Safe-mode call ~1.36s with `assign_global`. Config files list (~3.17s) and file read (~2.39s) both repeat dev identity + `assign_global` (already_exists). Parallel auth calls drive duplicate role work; no document-specific heavy queries beyond role overhead.
- `logs/ade-start-config-builder-validation.log` — Startup roles registry sync ~2s. Validation flow: `/validate` POST ~3.1s with repeated `assign_global`; then `/configurations/{id}/runs` POST triggers env build and run prepare; total request ~14.9s. Pool emitted warning about unclosed aioodbc connection during/after run. Safe-mode call still ~1.3s with repeated role assignment. Heavy repeated role work plus long build pipeline dominate latency.
- `logs/ade-start-config-builder-test-run.log` — Startup roles registry sync ~2s. `/documents` list 4.1s and `/documents/{id}/sheets` 3.6s, both repeating `assign_global`. Run start (`/configurations/{id}/runs` with document) ~12.2s even with active build, still redoes role assignment. Safe-mode fetch ~1.5s. Subsequent run outputs/summary/logfile calls each ~1.3–1.5s and also redo `assign_global`. Heavy role duplication plus long run prep dominate.
- `logs/ade-upload-document.log` — Safe-mode call ~1.35s with role lookup/assign. Document upload POST takes ~4.2s, then documents list GET ~3.9s; both repeat dev identity and `assign_global` (already_exists). Role overhead present despite auth disabled.
- `logs/ade-upload-multiple-documents.log` — Sequence of document uploads: multiple `/documents` POSTs each ~3.7–4.2s, all repeating `assign_global` despite auth disabled. Safe-mode call ~1.83s also redoes role assignment. Final documents list GET ~3.6s. Throughput dominated by per-request role overhead.
- `logs/ade-filter-documents-by-status.log` — Startup shows roles registry sync (~2s). Auth disabled but dev identity still triggers `roles.global.get_by_slug` + `assign_global` (already_exists) on `/api/v1/system/safe-mode`, leading to ~1.3s request time; no document filter actions captured (log likely truncated/limited).
- `logs/ade-filter-by-recently-run.log` — Startup roles registry sync ~2.1s. `/documents?sort=-last_run_at` takes ~4.37s with role lookup/assign. Safe-mode fetch ~1.4s also repeats `assign_global`. Same repeated role overhead pattern.
- `logs/uploads/ade-documents-screen-post-caching.log` — Post-caching documents screen: single `/api/v1/bootstrap` (~3.4s) covering safe-mode/workspaces/roles, followed by documents GET (~1.76s). Registry sync only at startup; roles/principal cached; no extra workspaces/safe-mode calls.
- `logs/uploads/ade-bootstrap-latency-post-cache.log` — Bootstrap + documents after cache fixes: `/api/v1/bootstrap` ~2.12s with most time in `auth.resolve_user` (~0.8s) then global perms/roles (~0.14s), workspaces (~0.07s), safe-mode (~0.13s). Documents GET ~2.9s for 1 document: workspace permission fetch (~0.55s) then list + last_run attach (~2.3s total). Registry sync only at startup; no redundant workspaces/safe-mode calls.
- `logs/uploads/ade-documents-screen-last-run-windowed.log` — Post windowed last_run query: `/api/v1/bootstrap` ~2.10s (similar shape, `auth.resolve_user` ~0.84s). Documents GET ~2.86s for 1 document; last_run query now ~0.07s and attach completes in ~0.13s. Remaining time dominated by workspace permission fetch (~0.55s) plus base documents query. Registry sync remains startup-only.

---

## 7. Backend code hotspots (in-progress)

- `features/auth/service.py` — Request-scoped identity cache now active; no `assign_global` chatter in the new baseline. Still worth confirming `get_current_identity` and bootstrap reuse the same permission payload to avoid repeated sub-calls.
- `features/roles/service.py` — Registry sync now startup-only. New baseline shows multiple `roles.permissions.global.for_principal` + `roles.global_slugs.for_user` calls inside one bootstrap request; profile/hoist those to a single fetch per request if possible to trim the ~3.4s bootstrap duration. Registry sync now re-seeds when system roles are missing and global-role cache falls back to DB when cached IDs disappear.
- `features/documents/service.py` — Documents GET now ~1.76s (empty list) after bootstrapping; with data ~2.9s driven by last_run attach + workspace permission lookup. Last-run attachment now uses a windowed query (`row_number` over runs) to fetch only the latest per document.
- Request fan-out — Frontend now uses `/api/v1/bootstrap` and avoids extra workspaces/safe-mode calls on load. Remaining goal is to shave bootstrap latency toward <1s by deduplicating permission/global-role reads and checking DB round-trips.

---

## 8. Proposed optimizations (draft)

- Registry sync: cache by persisted version (e.g., system setting `roles-registry-version` or checksum of `PERMISSIONS`/`SYSTEM_ROLES`) and process-local TTL. Only force sync when version changes or on startup with `force=True`.
- Global role lookup/assignment: cache global role slug→id in-memory with TTL; add `assign_global_if_missing` that short-circuits when assignment exists (query once via unique constraint). Use per-request memoization of principal/permissions in FastAPI dependency or request state/contextvar.
- Request-scoped identity cache: create a dependency that resolves dev identity/user/principal/permissions once per request and reuses in downstream routes (session, workspaces, safe-mode, documents, etc.).
- Bootstrap endpoint: `/api/v1/bootstrap` (or similar) returning session user + permissions + global roles + workspace memberships + safe-mode in one payload; frontend uses this instead of parallel calls. If adding, update OpenAPI and regenerate types (`ade openapi-types`).
- Documents list: optional improvement to latest-run lookup via `row_number()` per document and index on `runs(workspace_id, input_document_id, finished_at DESC, started_at DESC)` to keep attach fast at scale.

Next steps (implementation plan):
1) Implement registry version/TTL cache to stop per-request sync.
2) Add global role id cache + `assign_global_if_missing` guard; memoize principal/permissions per request.
3) Add request-scoped identity dependency and wire routes to reuse it.
4) Add bootstrap endpoint + schema/types; update frontend to use it (or server-side cache fallback if deferring frontend change).
5) Optional: refine documents last_run query/index if needed after auth/roles fixes.

---

## 9. Implementation tasks (in-progress)

- Registry caching: add version/TTL guard to `sync_permission_registry` (persisted marker + process-local TTL) to avoid per-request sync; cover with tests. — implemented: SHA-256 fingerprint persisted via `roles-registry-version`; TTL 10m process cache + persisted skip; added reseed guard when DB tables are empty even if cache is warm.
- Global role caching: add slug→role_id cache with TTL; introduce `assign_global_if_missing` to early-return when assignment exists; ensure `ensure_dev_identity` and initial-setup paths use it. — implemented (role cache with TTL, dev identity and initial setup paths use `assign_global_role_if_missing`; SSO auto-provision path updated too).
- Request-scoped identity cache: FastAPI dependency/contextvar to memoize user/principal/permissions per request; wire session/workspaces/safe-mode/documents/runs to reuse. — implemented baseline contextvar memoization in `get_current_identity` plus cached global+workspace permissions in `require_global`/`require_workspace`; per-request caches now reset to avoid cross-request leakage.
- Bootstrap endpoint: design `/api/v1/bootstrap` (user/profile, permissions, roles, workspaces, safe-mode) and update OpenAPI/types + frontend; or server-side cache if deferring frontend. — implemented endpoint/schema + registered router; OpenAPI/types regenerated; frontend now consumes bootstrap in `useSessionQuery` to seed workspaces + safe-mode caches (fixed queryFn bug).
- Last-run query/index: evaluate `runs` index on `(workspace_id, input_document_id, finished_at desc, started_at desc)` and optional CTE to pull latest run per document. — added index and simplified last_run query ordering.

Next tactical steps:
- Profile `/api/v1/bootstrap` (~2.1s in latest capture) to isolate remaining time—`auth.resolve_user` dominates (~0.8s). Resolution path now uses a lightweight user fetch (no credential/identity join); re-measure bootstrap after this change and continue trimming global perms/roles duplication to target <1s.
- Verify documents list latency with non-empty data (current capture: ~2.9s with 1 document including last_run attach). Windowed last_run query now limits to latest per document; re-measure with data and ensure runs index is used. Look for request-level cache reuse for workspace permissions if still slow.
- Testing note: when running integration tests that assert permission enforcement, export `ADE_AUTH_DISABLED=false` (local env defaults may be true for dev). Bootstrap TypeError fixed by calling `get_global_permissions_for_principal` with the principal only; bootstrap integration test now passes.

---

## 10. Request-scoped cache & bootstrap design (draft)

- Identity cache dependency: create `get_cached_identity` (contextvar + request.state) that runs `ensure_dev_identity`/auth once per request, reuses principal/permissions/global roles, and exposes a dataclass with user, principal_id, permissions, global_roles. All routes use this instead of re-running auth/roles.
- Permissions cache: memoize global permissions for the principal within the request, optionally with a small TTL for background tasks.
- Bootstrap endpoint: `/api/v1/bootstrap` returns `{ user, profile, principal_id, global_roles, permissions, workspaces: {...}, safe_mode }`, leveraging the cached identity; workspace memberships reused from the same call.
- Wiring: session/workspaces/safe-mode/documents/runs/configs to accept cached identity (dependency override) rather than fresh service calls; maintain compatibility with auth-enabled mode.

> Note: To regenerate frontend OpenAPI types, activate the venv first (`source .venv/bin/activate`) so `ade openapi-types` is available.
