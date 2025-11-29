> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * When you make a design/architecture decision, **update this document first**, then the relevant supporting doc, then the code.
> * Prefer small, incremental commits aligned to checklist items.
> * Do not introduce new navigation/streaming patterns outside the ones defined here and in the supporting specs.

---

## Related Documents (read alongside this workpackage)

These documents live in the same folder as this workpackage:

- `020-ARCHITECTURE.md` – High-level architecture, folder structure, data layer, and diagrams.
- `030-UX-FLOWS.md` – UX goals and detailed flows for Workspace, Documents, Run Detail, and Config Builder.
- `040-DESIGN-SYSTEM.md` – Design tokens, visual language, and component guidelines.
- `050-RUN-STREAMING-SPEC.md` – Run streaming behavior, `RunStreamState`, SSE/NDJSON handling, and replay rules.
- `060-NAVIGATION.md` – Custom navigation/router design (vanilla React + history), route definitions, and URL patterns.
- `070-TEST-PLAN.md` – Test strategy, coverage expectations, and concrete test cases.
- `080-MIGRATION-AND-ROLLOUT.md` – Archive strategy, parity checklist, and go-live plan vs `ade-web-legacy`.

If a section here feels too high-level, check the corresponding document for details.

---

## Work Package Checklist

> **Agent note:**  
> Add brief status notes inline when helpful, e.g.  
> `- [x] Archive strategy — existing app moved to apps/ade-web-legacy and CI updated (2025-12-03)`

### Planning & setup

- [ ] Capture requirements and UX goals for **Config Builder** and **Documents & Runs** flows (upload → run → review → download).  
      (See `030-UX-FLOWS.md`.)
- [ ] Decide and document archive strategy for the existing `apps/ade-web`.  
      (See `080-MIGRATION-AND-ROLLOUT.md`.)
- [ ] Rename/archive the old app (e.g. `apps/ade-web-legacy`) and scaffold the new `apps/ade-web` baseline.
- [ ] Align tooling/CI/scripts to the new app (dev, build, test).

### Architecture & foundations

- [ ] Land target folder structure and base TypeScript/React config (strict mode, aliases, testing setup).  
      (See `020-ARCHITECTURE.md`.)
- [ ] Implement navigation foundation (custom history‑based router with typed route registry; **no React Router**).  
      (See `060-NAVIGATION.md`.)
- [ ] Implement shared providers (Auth, Query, Theme, Toast, Run Streams) and wire them in `AppShell`.
- [ ] Establish design system foundations: tokens (spacing, color, typography), layout primitives, core components (Button, Input, Tabs, Dialog, Toast).  
      (See `040-DESIGN-SYSTEM.md`.)

### Run streaming & telemetry

- [ ] Implement `RunStreamState` + `runStreamReducer` as shared primitives.  
      (See `050-RUN-STREAMING-SPEC.md`.)
- [ ] Implement `RunStreamProvider` and `useRunStream(runId)` hook (live SSE + replay).
- [ ] Implement `useRunTelemetry(runId)` for incremental NDJSON replay (historical runs).
- [ ] Add backpressure/buffering logic (line clamping, batch updates) for large logs.
- [ ] Add unit tests for reducers and streaming hooks.  
      (See `070-TEST-PLAN.md`.)

### Shared run experience components

- [ ] Implement `RunConsole` with filters (origin, level, text search) and follow‑scroll.  
      (UX details in `030-UX-FLOWS.md`, visual details in `040-DESIGN-SYSTEM.md`.)
- [ ] Implement `RunTimeline` (build + run phases, durations, status coloring).
- [ ] Implement `RunSummaryPanel` (table summary, validation summary, status).
- [ ] Implement error‑first debug behavior (auto jump to first error, context window, highlighting).
- [ ] Implement deep‑link support (`runId` + sequence) and “replay to here” behavior.  
      (Deep-link behavior in `050-RUN-STREAMING-SPEC.md` + `060-NAVIGATION.md`.)

### Screens & UX flows

- [ ] Implement Workspace Home screen (entry point, navigation to Documents/Config Builder).  
      (Flows in `030-UX-FLOWS.md`.)
- [ ] Implement Documents screen:
  - [ ] Document list with status, last run summary, and quick actions.
  - [ ] File upload flow with clear state (queued, uploaded, validation pending, last run).
  - [ ] Per‑document “Runs & Outputs” drawer/panel (run history + download surface).
  - [ ] Run creation from document (start run, show live streaming progress).
  - [ ] Download surface (original file, normalized output, log archive, error reports).
- [ ] Implement Run Detail screen:
  - [ ] Live + replay view (SSE + NDJSON).
  - [ ] Console, timeline, run insights shared with other screens.
- [ ] Implement Config Builder screen on top of new foundations:
  - [ ] Editor/workbench layout.
  - [ ] `useWorkbenchRun` wired to `useRunStream`.
  - [ ] Shared console/timeline/summary components.

### Integration & cleanup

- [ ] Ensure Documents, Run Detail, and Config Builder all use **shared** run UI and stream infrastructure.
- [ ] Remove/avoid legacy streaming and console formatting logic; reference only new primitives.
- [ ] Add basic integration tests for key flows (upload → run → download; edit config → run → debug error).  
      (See `070-TEST-PLAN.md`.)
- [ ] Add developer documentation (README and high‑level architecture notes) in the new app.
- [ ] Confirm old `apps/ade-web-legacy` is effectively quarantined (no accidental re‑use in new code).  
      (See `080-MIGRATION-AND-ROLLOUT.md`.)

---

# ADE Web Refactor (from scratch)

## 1. Objective

**Goal**  
Rebuild `apps/ade-web` from the ground up with a clean architecture, modern design system, and first‑class run/build event streaming – covering both:

1. **Config authors** working in the **Config Builder**.
2. **End users** working in the **Documents** pane who:
   - Upload files,
   - Start runs,
   - Review progress (including logs & validation),
   - Download original and normalized files plus log output and error reports.

We are allowed to rename/archive the current app and rebuild from scratch to “do it right”.

You will:

- Archive/rename the current `apps/ade-web` and create a **new** `apps/ade-web` React+Vite+TypeScript app that matches our standards.
- Establish:
  - A clear app shell (navigation, providers, auth).
  - A reusable design system.
  - A shared run streaming and telemetry foundation (`AdeEvent` SSE + NDJSON).
- Reimplement priority experiences:
  - Workspace Home.
  - Documents (file upload & runs).
  - Run Detail.
  - Config Builder.

For more context on architecture and UX goals, see:

- `020-ARCHITECTURE.md`  
- `030-UX-FLOWS.md`

---

## 2. Context (What you are starting from)

Current `apps/ade-web`:

- Routerless, screen‑first Vite app with ad‑hoc navigation helpers and manual `window.history` usage.
- Run/build streaming logic is embedded inside Config Builder’s Workbench; it owns its own reducer + SSE + abort wiring.
- Documents screen has limited UX for:
  - Uploading files.
  - Starting new runs.
  - Understanding progress/errors.
  - Finding and downloading normalized outputs/logs later.
- Design system is minimal; theming and spacing/typography are inconsistent.

Backend and shared foundations:

- Unified `AdeEvent` event stream for build/run/logs:
  - SSE endpoint: `/runs/{run_id}/events?stream=true&after_sequence=0`.
  - Persisted NDJSON telemetry: `events.ndjson`.
- Existing frontend primitives:
  - `RunStreamState`, `runStreamReducer`, `streamRunEvents`.
  - `fetchRunTelemetry` for historical NDJSON.
  - Console formatters for build/run logs.

Hard constraints:

- Keep **Vite + React + TypeScript**.
- **No React Router** – stay with “vanilla React” + custom navigation.
- Use ADE API SSE/NDJSON (no custom protocol).
- Consume generated OpenAPI types from ADE tooling.

(See `020-ARCHITECTURE.md` and `060-NAVIGATION.md` for more detail.)

---

## 3. Target Architecture / Structure

We keep a **single** `apps/ade-web` app and archive the old one to `apps/ade-web-legacy`. The new app uses a layered structure with clear separation of concerns.

High‑level structure:

```text
apps/
  ade-web-legacy/          # archived existing app (read-only)
  ade-web/                 # new app root
    src/
      app/
        AppShell.tsx
        nav/               # custom router (no React Router)
        providers/
      screens/             # Workspace, Documents, RunDetail, ConfigBuilder
      features/            # runs, documents, configs, auth, etc.
      ui/                  # design system primitives
      shared/              # cross-cutting utilities
      schema/              # curated type exports & view models
      test/                # testing setup & helpers
```

Details on each layer, data flow, and example diagrams live in `020-ARCHITECTURE.md`.

### 3.1 Navigation (custom, vanilla React)

* Typed route registry in `app/nav/routes.ts`.
* History-based navigation helpers in `app/nav/navigation.ts`.
* `useNavigation()` hook that exposes `{ route, navigate, replace }`.
* No React Router or other 3rd-party routing package.

Full spec (route shapes, URL patterns, edge cases) is defined in `060-NAVIGATION.md`.

### 3.2 Data & API layer

* React Query for fetching/caching server state.
* `shared/api-client` wraps fetch/Axios and uses generated ADE types.
* `schema/` re-exports curated types and view models so screens/components don’t import from raw generated files.

### 3.3 Design System & Theming

* CSS variables for tokens (colors, typography, spacing, radii, shadows).
* UI primitives in `ui/components` and layout primitives in `ui/layout`.
* Accessible by default (keyboard, ARIA), consistent hover/active/disabled states.

See `040-DESIGN-SYSTEM.md` for token definitions, component behavior, and layout guidelines.

---

## 4. UX Design (high level)

### 4.1 Design Principles

* **Clarity:** Every screen answers “Where am I?”, “What’s happening?”, “What next?”.
* **Cohesive streaming experience:** Runs started anywhere (Documents, Config Builder) feel consistent.
* **Task-first:** Config authors vs Document users flows are optimized for their tasks.
* **Progress & reassurance:** Users always see run status and whether outputs are ready.
* **Error-first debugging:** It’s trivial to jump to the first failure and see surrounding context.

Concrete flows and more detailed UX guidance live in `030-UX-FLOWS.md`.

### 4.2 Key flows (summary)

* **Documents:**

  * Upload → Start run → Watch progress → Review results → Download outputs/logs.
* **Run Detail:**

  * Inspect status, phases, logs, validation; replay history; share deep links.
* **Config Builder:**

  * Edit config → Validate → Run → Investigate failures (using shared run components).
* **Workspace Home:**

  * Orientation and quick access to recent runs/documents/configs.

---

## 5. Run Streaming & Telemetry (summary)

We centralize all run streaming concerns in `features/runs/stream`.

Core pieces:

* `RunStreamState` and `runStreamReducer`.
* `RunStreamProvider` and `useRunStream(runId)` for live SSE.
* `useRunTelemetry(runId)` for replay via NDJSON.
* Backpressure: console line buffer caps, batched updates, optional virtualization later.
* Deep linking: `runId` + `sequence` → replay to that state before rendering.

`050-RUN-STREAMING-SPEC.md` defines the exact reducer shape, state machine, error handling, and replay semantics.

---

## 6. Screens & UX Flows (summary)

* **Documents:**

  * Document list displaying name, last run status, and quick “Open / Run” actions.
  * Upload UI with progress, clear error messaging, and immediate post-upload guidance (“Start a run”).
  * Document detail view with:

    * Run history.
    * Live run card for active runs (timeline + mini console).
    * Outputs & downloads section (original, normalized, logs, error reports).

* **Run Detail:**

  * Full run inspection with `RunTimeline`, `RunConsole`, and `RunSummaryPanel`.
  * Sequence scrubber for replay.
  * “Jump to first error” and deep links.

* **Config Builder:**

  * Editor/workbench with shared run panel.
  * Relies on `useWorkbenchRun` → `useRunStream`.

`030-UX-FLOWS.md` includes step‑by‑step flows and per‑screen behavior.

---

## 7. Implementation Plan & Milestones

We implement in phases (see checklist for tasks):

1. **Phase 1 – Archive & scaffold**
2. **Phase 2 – Architecture & design system**
3. **Phase 3 – Run streaming foundation**
4. **Phase 4 – Documents & runs UX**
5. **Phase 5 – Config Builder & Run Detail**
6. **Phase 6 – Hardening, tests, and cutover**

For migration steps and go‑live criteria, see `080-MIGRATION-AND-ROLLOUT.md`.

---

## 8. Non‑Goals / Later Phases

(Details in `020-ARCHITECTURE.md` and `030-UX-FLOWS.md` for future expansions.)

Out of scope for this workpackage (may be separate WPs later):

* Workspace “live activity” feed.
* Active‑runs wallboard.
* Cross‑run comparison/regression UI.
* Advanced analytics (phase performance trends).
* Deep remediation hints beyond basic inline suggestions.

---

## 9. Notes for Agents

* Use TypeScript strict mode; avoid `any`.
* Put all run streaming logic into `features/runs/stream`; screens consume it via hooks/components.
* Don’t reinvent navigation or streaming in individual screens – update `060-NAVIGATION.md` / `050-RUN-STREAMING-SPEC.md` if you need to extend them.
* When in doubt about UX behavior, consult `030-UX-FLOWS.md` and update it if the plan changes.
* Follow the test expectations in `070-TEST-PLAN.md` before marking major features as done.

