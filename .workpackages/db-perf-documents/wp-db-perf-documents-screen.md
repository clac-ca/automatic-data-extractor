> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [ ] Baseline current auth/roles/documents call timings and DB queries for the documents screen (session, workspaces, safe-mode, documents).
* [ ] Cache/short-circuit roles registry sync and global role slug lookup so they do not run per request.
* [ ] Make global role assignment + principal/permission resolution idempotent within a request (early exit when already assigned, reuse cached principal/permissions).
* [ ] Add a backend bootstrap path or shared cache to avoid multiple auth/roles round-trips for one screen; update OpenAPI types and frontend usage.
* [ ] Optimize documents list DB path (including last_run join) and add regression safeguards/metrics for latency.
* [ ] Deep-dive `logs/ade-startup.log` and summarize perf findings in Section 6.
* [ ] Deep-dive `logs/ade-initial-setup.log` and summarize perf findings in Section 6.
* [ ] Deep-dive `logs/ade-load-workspaces-page.log` and summarize perf findings in Section 6.
* [ ] Deep-dive `logs/ade-load-workspace-settings.log` and summarize perf findings in Section 6.
* [ ] Deep-dive `logs/ade-load-workspace-settings-members-tab.log` and summarize perf findings in Section 6.
* [ ] Deep-dive `logs/ade-load-workspace-settings-roles-tab.log` and summarize perf findings in Section 6.
* [ ] Deep-dive `logs/ade-creating-workspace.log` and summarize perf findings in Section 6.
* [ ] Deep-dive `logs/ade-creating-config-from-template.log` and summarize perf findings in Section 6.
* [ ] Deep-dive `logs/ade-load-config-builder-page.log` and summarize perf findings in Section 6.
* [ ] Deep-dive `logs/ade-load-config-builder-editor.log` and summarize perf findings in Section 6.
* [ ] Deep-dive `logs/ade-start-config-builder-validation.log` and summarize perf findings in Section 6.
* [ ] Deep-dive `logs/ade-start-config-builder-test-run.log` and summarize perf findings in Section 6.
* [ ] Deep-dive `logs/ade-upload-document.log` and summarize perf findings in Section 6.
* [ ] Deep-dive `logs/ade-upload-multiple-documents.log` and summarize perf findings in Section 6.
* [x] Deep-dive `logs/ade-filter-documents-by-status.log` and summarize perf findings in Section 6 — log only covers startup + `/system/safe-mode`; noted role overhead.
* [ ] Deep-dive `logs/ade-filter-by-recently-run.log` and summarize perf findings in Section 6.

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

---

## 6. Log deep-dive notes (fill as you analyze each file)

- `logs/ade-startup.log` — TODO
- `logs/ade-initial-setup.log` — TODO
- `logs/ade-load-workspaces-page.log` — TODO
- `logs/ade-load-workspace-settings.log` — TODO
- `logs/ade-load-workspace-settings-members-tab.log` — TODO
- `logs/ade-load-workspace-settings-roles-tab.log` — TODO
- `logs/ade-creating-workspace.log` — TODO
- `logs/ade-creating-config-from-template.log` — TODO
- `logs/ade-load-config-builder-page.log` — TODO
- `logs/ade-load-config-builder-editor.log` — TODO
- `logs/ade-start-config-builder-validation.log` — TODO
- `logs/ade-start-config-builder-test-run.log` — TODO
- `logs/ade-upload-document.log` — TODO
- `logs/ade-upload-multiple-documents.log` — TODO
- `logs/ade-filter-documents-by-status.log` — Startup shows roles registry sync (~2s). Auth disabled but dev identity still triggers `roles.global.get_by_slug` + `assign_global` (already_exists) on `/api/v1/system/safe-mode`, leading to ~1.3s request time; no document filter actions captured (log likely truncated/limited).
- `logs/ade-filter-by-recently-run.log` — TODO
