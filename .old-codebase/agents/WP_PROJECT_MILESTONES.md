# Work Package: Project Completion Roadmap

> **Agent instructions:**
> 1. Open this work package before you start or resume any task that touches ADE’s launch readiness.
> 2. Update the checkboxes in place as you land work (use `[x]` when a line is done, add dated notes if helpful).
> 3. Keep the handoff log current: after each session, summarize what you shipped under “Completed in Last Session” and set a single actionable item under “Next Step for Incoming Agent”. Clear or replace prior entries instead of appending long histories.
> 4. If you discover scope changes, append clarifying bullets beneath the impacted item instead of deleting history.
> 5. When every checkbox under a numbered milestone is complete, annotate the heading with `(complete – YYYY-MM-DD)`.

## Session Handoff

### Completed in Last Session
- Introduced `AppShell` parent layout and refactored workspace surfaces to register chrome declaratively; router now wraps authenticated routes with the shared shell and `HomeRedirectRoute` relies on it for baseline scaffolding.
- Moved all authenticated routes into feature-owned `*.route.tsx` modules (auth, workspaces, documents, configurations, setup) and trimmed the legacy `app/routes` directory to shared fallbacks only.
- Centralized workspace navigation metadata inside `workspaces/sections.ts` and moved TanStack Query keys/hooks into feature `api/keys.ts` + `api/queries.ts` modules so chrome and cache strategy stay consistent.

### Next Step for Incoming Agent
- Build the shared `PageHeader` primitive and replace per-route header markup so sections consume consistent chrome.

## Summary
ADE authenticates, stores uploads, and lets analysts author extraction scripts, but the frontend spine is still improvised: authenticated routes stitch their own shells, navigation metadata lives inside feature folders, route files mix naming conventions, and query keys sit inside ad-hoc hooks. That fragmentation makes core milestones (workspace settings, upload-to-run orchestration, durable jobs, and the production processor) harder to land without rework. This pass confirms the gaps and sequences the minimum fixes: stand up a shared shell and routing model, deliver real workspace administration, build the configurable upload-to-run flow, move jobs onto an asynchronous rail, harden configuration safety, and finish the production processor with basic operational guardrails.

## Milestones

### 1. Normalize the frontend shell and routing spine
- [x] Establish an `AppShell` parent route that renders `GlobalTopBar`, the nav rails, and an `<Outlet>` once so authenticated pages such as `HomeRedirectRoute` no longer craft full-screen wrappers or headers by hand.【F:frontend/src/app/AppRouter.tsx†L1-L70】【F:frontend/src/app/layouts/WorkspaceLayout.tsx†L140-L260】【F:frontend/src/features/workspaces/routes/home-redirect.route.tsx†L1-L48】
- [x] Collapse `frontend/src/app/routes/*` into feature-owned route modules that follow the `*.route.tsx` convention, removing cross-tree imports like `WorkspacesIndexRoute` reaching into feature hooks via long relative paths.【F:frontend/src/app/AppRouter.tsx†L1-L70】【F:frontend/src/features/workspaces/routes/workspaces-index.route.tsx†L1-L108】
- [x] Standardize route filenames so we stop mixing `DocumentsRoute.tsx`, `WorkspacesIndexRoute.tsx`, and nested `documents/DocumentsTable.tsx` helpers in the same folder; co-locate feature routes under `features/*/routes/*.route.tsx` to align name and path conventions.【F:frontend/src/features/documents/routes/documents.route.tsx†L1-L520】【F:frontend/src/features/workspaces/routes/workspaces-index.route.tsx†L1-L108】
- [x] Centralize navigation metadata in a single schema (ids, labels, permissions, iconography) instead of `workspaces/navigation.ts`, and let route handles expose layout hints (secondary rail) so the shell stays declarative.【F:frontend/src/app/workspaces/sections.ts†L1-L236】
- [x] Ship a reusable `PageHeader` with title and primary action slots so content panes stop duplicating `<h1>` markup that the shell already renders via breadcrumbs.【F:frontend/src/app/layouts/WorkspaceLayout.tsx†L320-L356】【F:frontend/src/features/documents/routes/documents.route.tsx†L1-L360】
- [x] Move TanStack Query keys and hooks into `api/queries.ts` + `api/keys.ts` modules per feature, align cache policies, and wire error boundaries now that keys aren’t hidden inside custom hooks.【F:frontend/src/features/documents/api/queries.ts†L1-L46】【F:frontend/src/features/workspaces/api/queries.ts†L1-L21】
- [x] Replace the repo-wide `ui/index.ts` barrel with explicit exports so imports become grep-friendly (`@/shared/ui/Button` etc.) instead of ambiguous `../../ui` shortcuts.【F:frontend/src/features/documents/routes/documents.route.tsx†L18-L24】

### 2. Ship real workspace settings
- [x] Replace the placeholder workspace settings route with concrete screens for General, Members, and Roles so navigation stops landing on generic "coming soon" copy.【F:frontend/src/features/workspaces/routes/workspace-settings.route.tsx†L1-L212】
- [x] Bind members management to `/workspaces/{workspace_id}/members` (list, invite, resend, remove) using optimistic mutations similar to the document table so operators see immediate feedback.【F:frontend/src/features/workspaces/components/WorkspaceMembersSection.tsx†L1-L292】
- [x] Implement role catalog, create/update/delete, and assignment flows on top of the existing role endpoints with guardrails for built-in roles before we layer richer permissions.【F:frontend/src/features/workspaces/components/WorkspaceRolesSection.tsx†L1-L330】

### 3. Wire uploads to configurable runs
- [x] Reshape the documents workspace so each file exposes a primary "Run extraction" flow alongside bulk controls instead of stopping at upload/delete utilities.【F:frontend/src/features/documents/routes/documents.route.tsx†L1-L360】【F:frontend/src/features/documents/components/DocumentsTable.tsx†L1-L220】
- [ ] Add a run-settings drawer beside the CTA that captures sheet selection, one-or-many configuration picks, and advanced flags before dispatch, persisting the last-used choices per document for reruns.【F:frontend/src/features/documents/routes/documents.route.tsx†L284-L474】【F:frontend/src/features/documents/api/queries.ts†L1-L46】
- [ ] Extend job submission contracts to accept those advanced options and store them on the job record so the UI can summarise exactly what ran.【F:ade/features/jobs/schemas.py†L28-L56】【F:ade/features/jobs/router.py†L35-L179】
- [x] Pull per-document job history via `input_document_id` filtering and surface status chips plus last-run metadata inline so operators see whether a file already processed or is still queued.【F:frontend/src/features/documents/routes/documents.route.tsx†L360-L520】【F:frontend/src/features/jobs/hooks/useJobs.ts†L1-L60】

### 4. Stand up the asynchronous job rail
- [ ] Move `JobsService.submit_job` off the request thread by persisting work to a queue and letting workers perform extraction so API calls stay snappy on large documents.【F:ade/features/jobs/service.py†L49-L143】
- [ ] Model comparison runs as a parent record with child executions per configuration so multi-config submissions fan out cleanly without duplicating client logic.【F:ade/features/jobs/service.py†L87-L143】【F:ade/features/jobs/schemas.py†L28-L56】
- [ ] Flesh out `ade/workers/run_jobs.py` with startup/shutdown hooks, health checks, and CLI controls so operations can scale workers alongside the API.【F:ade/workers/run_jobs.py†L1-L86】
- [ ] Expand job read endpoints (streaming/polling) so the upload screen and future jobs hub can watch live progress across parent + child runs.【F:ade/features/jobs/router.py†L35-L179】

### 5. Make configurations run-safe
- [ ] Ensure the configuration workspace lets analysts choose stable versions and view execution history so they know what will run from the upload drawer.【F:frontend/src/features/configurations/routes/configurations.route.tsx†L1-L208】【F:frontend/src/features/configurations/components/ConfigurationScriptPanel.tsx†L1-L240】
- [ ] Tighten backend validation to reject unknown parameters and enforce version locks so stored scripts align with the processor contract before jobs queue.【F:ade/features/configurations/service.py†L140-L240】
- [ ] Surface configuration metadata (supported sheets, comparison readiness) through the API so the run-settings drawer can pre-fill sensible defaults instead of relying on free-form text.【F:ade/features/configurations/service.py†L189-L240】【F:ade/features/jobs/service.py†L49-L143】

### 6. Finish the production processor and release basics
- [ ] Replace the stub processor with the real execution engine: sandbox scripts, emit structured outputs, and calculate comparison metrics the UI can display.【F:ade/features/jobs/processor.py†L1-L88】
- [ ] Persist artefacts, step timings, and diagnostics so retries and comparisons survive worker restarts and populate the jobs history surfaces.【F:ade/features/jobs/service.py†L111-L143】
- [ ] Add end-to-end tests that push representative spreadsheets through single and multi-configuration runs to keep the asynchronous rail honest.【F:ade/features/jobs/service.py†L87-L143】
- [ ] Package API and worker images with health checks plus logging/metrics hooks so operations can deploy the queue-backed system confidently.【F:ade/platform/logging.py†L1-L200】【F:ade/workers/run_jobs.py†L1-L86】

## Tricky part
Standing up the production extraction runtime with multi-configuration comparisons remains the riskiest milestone. It must safely sandbox arbitrary scripts, fan work out across the new job rail, and emit durable artefacts/metrics that the upload screen, configuration picker, and jobs hub all rely on—without losing observability. Nail that contract and the rest of the operator experience can trust what “run extraction” actually means.
