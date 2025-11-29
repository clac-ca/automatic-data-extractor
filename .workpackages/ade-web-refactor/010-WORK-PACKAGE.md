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
- `080-MIGRATION-AND-ROLLOUT.md` – Archive strategy, parity checklist, and go-live plan vs `apps/ade-web-legacy`.
- `090-FUTURE-WORKSPACES.md` – Future workspace selector/creation UX (explicitly out of scope for this workpackage).
- `100-CONFIG-BUILDER-EDITOR.md` – Detailed specification for the Config Builder / configuration editor (VS Code–like layout, behaviors, and run integration).
- `110-BACKEND-API.md` – Backend API surface, route groupings, and frontend integration conventions (including OpenAPI-generated types).


If a section here feels too high-level, check the corresponding document for details.

---

## Work Package Checklist

> **Agent note:**  
> Add brief status notes inline when helpful, e.g.  
> `- [x] Archive strategy — existing app moved to apps/ade-web-legacy and CI updated (2025-12-03)`

### Planning & setup

- [x] Capture requirements and UX goals for **Config Builder** and **Documents & Runs** flows (upload → run → review → download) — confirmed against `030-UX-FLOWS.md` (Documents list/detail with upload→run→review→download; Config Builder run panel shares console/timeline with Run Detail).  
      (See `030-UX-FLOWS.md`.)
- [x] Decide and document archive strategy for the existing `apps/ade-web` — archive to `apps/ade-web-legacy`, rename package to `ade-web-legacy`, keep `apps/ade-web` for the new build with static assets still landing in `apps/ade-api/src/ade_api/web/static` (`080-MIGRATION-AND-ROLLOUT.md`).  
      (See `080-MIGRATION-AND-ROLLOUT.md`.)
- [x] Rename/archive the old app (moved to `apps/ade-web-legacy`, renamed package/readme) and scaffolded new `apps/ade-web` baseline (fresh Vite+TS app with providers/nav/screen shells, lint/test/build wired).
- [x] Align tooling/CI/scripts to the new app (dev, build, test) — updated bundle scripts to target new `apps/ade-web` structure and avoid legacy references.

### Architecture & foundations

- [x] Land target folder structure and base TypeScript/React config (strict mode, aliases, testing setup) — new `apps/ade-web` scaffolded with `@app/@screens/@features/@ui/@shared/@schema/@test` aliases, Vite/Vitest/ESLint config, Navigation/Providers shells, and placeholder screens.  
      (See `020-ARCHITECTURE.md`.)
- [x] Implement navigation foundation (custom history‑based router with typed route registry; **no React Router**) — `Route` union per `060-NAVIGATION.md`, `parseLocation`/`buildUrl`, Link component, notFound handling, and AppShell wiring.  
      (See `060-NAVIGATION.md`.)
- [x] Implement shared providers (Auth, Query, Theme, Toast, Run Streams) and wire them in `AppShell` — baseline contexts with hooks and on-screen toast host ready for future data wiring.
- [x] Establish design system foundations: tokens (spacing, color, typography), layout primitives, core components (Button, Input, Tabs, Dialog, Toast) — tokens wired into global styles and baseline primitives added under `src/ui/components`/`src/ui/theme`.  
      (See `040-DESIGN-SYSTEM.md`.)

### Run streaming & telemetry

- [x] Implement `RunStreamState` + `runStreamReducer` as shared primitives — state model with sequences/derived placeholders and tested reducer scaffold.  
      (See `050-RUN-STREAMING-SPEC.md`.)
- [x] Implement `RunStreamProvider` and `useRunStream(runId)` hook (live SSE + replay) — provider + boundary with SSE attachment, error/completion handling, and buffered event intake.
- [x] Implement `useRunTelemetry(runId)` for incremental NDJSON replay (historical runs) — NDJSON fetch + chunk dispatch + completion/error handling.
- [x] Add backpressure/buffering logic (line clamping, batch updates) for large logs — capped buffers for events and console lines to avoid UI freezes.
- [x] Add unit tests for reducers and streaming hooks — reducer covered; hook tests pending once live wiring lands.  
      (See `070-TEST-PLAN.md`.)

### Shared run experience components

- [x] Implement `RunConsole` with filters (origin, level, text search) and follow‑scroll — initial console component with search/level filters and buffered lines; follow-scroll/polish to expand with real event formatting.  
      (UX details in `030-UX-FLOWS.md`, visual details in `040-DESIGN-SYSTEM.md`.)
- [x] Implement `RunTimeline` (build + run phases, durations, status coloring) — placeholder component consuming shared phase state.
- [x] Implement `RunSummaryPanel` (table summary, validation summary, status) — status/sequence badges and validation summary hook-ups.
- [x] Implement error‑first debug behavior (auto jump to first error, context window, highlighting) — console jump-to-first-error with buffered derivation of first error line.
- [x] Implement deep‑link support (`runId` + sequence) and “replay to here” behavior — sequence param replays NDJSON and sets view sequence; manual input control in Run Detail for replay.
      (Deep-link behavior in `050-RUN-STREAMING-SPEC.md` + `060-NAVIGATION.md`.)


### Screens & UX flows

- [x] Implement Workspace Home screen (entry point, navigation to Documents/Config Builder) — placeholder cards with shortcuts ready to be wired to data.
      (Flows in `030-UX-FLOWS.md`.)

- [ ] Implement Documents screen:
  - [x] Document list with status, last run summary, and quick actions — placeholder list with status badges and selection wired to detail panel.
  - [x] File upload flow with clear state (queued, uploaded, validation pending, last run) — upload panel stub adds documents and selects them (local storage stub pending real API).
  - [x] Per‑document “Runs & Outputs” drawer/panel (run history + download surface) — detail panel renders shared run components for selected doc.
  - [x] Run creation from document (start run, show live streaming progress) — stub start-run CTA updates runId/status and attaches stream.
  - [x] Download surface (original file, normalized output, log archive, error reports) — placeholder downloads list per run.

- [ ] Implement Run Detail screen:
  - [x] Live + replay view (SSE + NDJSON) — deep-link sequence replays NDJSON, live SSE otherwise.
  - [x] Console, timeline, run insights shared with other screens.

- [ ] Implement Config Builder screen on top of new foundations:
  - [x] VS Code–inspired layout per `100-CONFIG-BUILDER-EDITOR.md`: placeholder split with editor surface and run panel using shared components.
  - [x] `useWorkbenchRun` wired to `useRunStream` and `useRunTelemetry` — stub hook manages runId/startRun and attaches streaming boundary.
  - [x] Shared console/timeline/summary components in the bottom panel.
  - [ ] Validation error linking:
    - From run/validation results back to specific config sections/fields.

### Integration & cleanup

- [x] Ensure Documents, Run Detail, and Config Builder all use **shared** run UI and stream infrastructure (`features/runs/stream` + shared components).
- [ ] Remove/avoid legacy streaming and console formatting logic; reference only new primitives.
- [x] Add basic integration tests for key flows (upload → run → download; edit config → run → debug error) — RTL tests cover Documents selection/upload/run, Config Builder run trigger, run stream hook; add more as flows harden.  
      (See `070-TEST-PLAN.md`.)
- [x] Add developer documentation (README and high‑level architecture notes) in the new app — see `apps/ade-web/DEVELOPER.md`.
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
  - Config Builder (VS Code–like configuration editor).

For more context on architecture and UX goals, see:

- `020-ARCHITECTURE.md`  
- `030-UX-FLOWS.md`  
- `100-CONFIG-BUILDER-EDITOR.md`

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

Workspace selection/creation UX and workspace management flows are **explicitly deferred** to `090-FUTURE-WORKSPACES.md` and are **out of scope** for this workpackage.

(See `020-ARCHITECTURE.md`, `060-NAVIGATION.md`, and `090-FUTURE-WORKSPACES.md` for more detail.)

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
````

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

Concrete flows and more detailed UX guidance live in `030-UX-FLOWS.md` and `100-CONFIG-BUILDER-EDITOR.md`.

### 4.2 Key flows (summary)

* **Documents:**

  * Upload → Start run → Watch progress → Review results → Download outputs/logs.

* **Run Detail:**

  * Inspect status, phases, logs, validation; replay history; share deep links.

* **Config Builder:**

  * VS Code–inspired editor:

    * Explorer (config structure).
    * Editor tabs.
    * Bottom run/validation panel.
  * Edit config → Validate → Run → Investigate failures using shared run components and validation → editor linking.

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

* **Config Builder (high-level summary):**

  * Editor/workbench with VS Code–like layout per `100-CONFIG-BUILDER-EDITOR.md`:

    * Left explorer for config structure.
    * Center editor tabs (code and/or schema-driven forms).
    * Bottom run panel with `RunSummaryPanel`, `RunTimeline`, `RunConsole`, and Validation tab.
  * Runs started in Config Builder are wired via `useWorkbenchRun` → `useRunStream`/`useRunTelemetry`.
  * Validation errors and run-time issues link back into the editor (explorer selection, tab activation, inline diagnostics).

`030-UX-FLOWS.md` and `100-CONFIG-BUILDER-EDITOR.md` include step‑by‑step flows and per‑screen behavior.

---

## 7. Config Builder Editor (focused summary)

For full detail, see `100-CONFIG-BUILDER-EDITOR.md`. This section summarizes the *required* shape of the Config Builder.

### 7.1 Layout

* **Header:** Config name, workspace context, Save / Validate / Run actions.
* **Left sidebar (Explorer):** Tree of config sections (sources, tables, mappings, validations, outputs, raw config).
* **Center (Editor):** Tabbed editor for selected sections:

  * Code editor and/or structured form editors.
  * Monospace where appropriate.
* **Bottom (Run Panel):** Resizable panel using shared run primitives:

  * Run tab (summary + timeline).
  * Console tab (logs).
  * Validation tab (per-table and per-section issues, linking back to editor).

### 7.2 Behavior

* VS Code–inspired:

  * Explorer with selection and expand/collapse.
  * Tabs for multiple open sections with dirty indicators.
  * Draggable splitter between Explorer/Editor and Editor/Run Panel.
* Keyboard:

  * `Ctrl/Cmd+S` to save.
  * `Ctrl/Cmd+F` for in-editor search.
  * `Ctrl/Cmd+Enter` to run (recommended).
* Validation:

  * Static validation within editor (field-level errors, inline messages).
  * Run-time validation in Run Panel; clicking an error opens the relevant config section and scrolls to the field/line where feasible.
* Streaming:

  * Runs triggered from Config Builder attach to run streams via `useWorkbenchRun` and `useRunStream`.
  * Run Panel updates live; errors are surfaced prominently (“error-first”).

This workpackage **requires** the Config Builder to follow this editor model; deviations should be reflected in `100-CONFIG-BUILDER-EDITOR.md` and then here.

---

## 8. Backend API Integration (summary)

Backend endpoints and their mapping to frontend features are documented in `110-BACKEND-API.md`. Key points:

* We use a single OpenAPI-derived type surface (`openapi.d.ts`) for all API request/response types.
* Feature-level API modules (`features/*/api/*.ts`) wrap the backend routes:

  * `authApi` / `sessionApi` → auth/session/bootstrap routes.
  * `workspacesApi` → workspace CRUD and membership.
  * `configsApi` → configuration list, metadata, files, validation, builds.
  * `documentsApi` → upload/list/download documents & sheets.
  * `runsApi` → run metadata, summary, events/logs/outputs.
* React Query hooks pull from these modules and feed screens and components in `screens/` and `features/*/components`.

No screen should call `fetch` directly against `/api/...` – all calls go through feature API wrappers using OpenAPI types.

---

## 9. Implementation Plan & Milestones

We implement in phases (see checklist for tasks):

1. **Phase 1 – Archive & scaffold**
2. **Phase 2 – Architecture & design system**
3. **Phase 3 – Run streaming foundation**
4. **Phase 4 – Documents & runs UX**
5. **Phase 5 – Config Builder & Run Detail**

   * Config Builder editor per `100-CONFIG-BUILDER-EDITOR.md`.
   * Run Detail with shared run components.
6. **Phase 6 – Hardening, tests, and cutover**

For migration steps and go‑live criteria, see `080-MIGRATION-AND-ROLLOUT.md`.

---

## 10. Non‑Goals / Later Phases

(Details in `020-ARCHITECTURE.md`, `030-UX-FLOWS.md`, `090-FUTURE-WORKSPACES.md`.)

Out of scope for this workpackage (may be separate WPs later):

* Workspace selector and creation UX (multi-workspace management).
* Workspace “live activity” feed.
* Active‑runs wallboard.
* Cross‑run comparison/regression UI.
* Advanced analytics (phase performance trends).
* Deep remediation hints beyond basic inline suggestions.
* Full config versioning/diff UI and command palette.

---

## 11. Non-Goals / Later Phases

(Details in `020-ARCHITECTURE.md`, `030-UX-FLOWS.md`, `090-FUTURE-WORKSPACES.md`.)

Out of scope for this workpackage (may be separate WPs later):

* Workspace selector and creation UX (multi-workspace management).
* Workspace “live activity” feed.
* Active-runs wallboard.
* Cross-run comparison/regression UI.
* Advanced analytics (phase performance trends).
* Deep remediation hints beyond basic inline suggestions.
* Full config versioning/diff UI and command palette.
* Comprehensive admin UIs for global roles/permissions and workspace role management.

---

## 12. Notes for Agents

* Use TypeScript strict mode; avoid `any`.
* Put all run streaming logic into `features/runs/stream`; screens consume it via hooks/components.
* Don’t reinvent navigation or streaming in individual screens – update `060-NAVIGATION.md` / `050-RUN-STREAMING-SPEC.md` if you need to extend them.
* For Config Builder, follow `100-CONFIG-BUILDER-EDITOR.md` and keep the VS Code–style layout and behaviors aligned.
* When in doubt about UX behavior, consult `030-UX-FLOWS.md` and `100-CONFIG-BUILDER-EDITOR.md` and update them if the plan changes.
* Follow the test expectations in `070-TEST-PLAN.md` before marking major features as done.
