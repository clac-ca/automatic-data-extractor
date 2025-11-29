> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * When you make a design/architecture decision, **update this document first**, then the code.
> * Prefer small, incremental commits aligned to checklist items.
> * Do not introduce new navigation/streaming patterns outside the ones defined here.

---

## Work Package Checklist

> **Agent note:**
> Add brief status notes inline when helpful, e.g.
> `- [x] Archive old app — apps/ade-web → apps/ade-web-legacy (2025‑12‑03)`

### 0. Planning & decisions

* [ ] Confirm and document foundational decisions:

  * [ ] **Navigation:** custom, “vanilla React” history-based router module (`useRoute`, `navigate`), no 3rd-party router.
  * [ ] **Styling:** CSS variables for design tokens + Tailwind (or utility classes) for layout/spacing.
  * [ ] **Data:** React Query for server data; React context/hooks for app + streaming state.
* [ ] Capture UX goals for:

  * [ ] Config Builder (existing mental model, but cleaned up).
  * [ ] Documents flow (upload → start run → watch progress → inspect results/errors → download outputs).

### 1. Archive old app & scaffold new baseline

* [ ] Move current `apps/ade-web` → `apps/ade-web-legacy`.
* [ ] Create a new `apps/ade-web` Vite + React + TypeScript project with strict TS settings.
* [ ] Update workspace scripts:

  * [ ] `pnpm dev ade-web` (or equivalent) runs the **new** app.
  * [ ] Provide an explicit script to run the legacy app (e.g. `dev:ade-web-legacy`).
* [ ] Ensure CI:

  * [ ] Builds and tests the new app.
  * [ ] Either runs or intentionally skips the legacy app with a clear comment.

### 2. Architecture & foundations

* [ ] Implement target folder structure (see Section 3).
* [ ] Implement navigation shell:

  * [ ] `AppShell` with top bar, workspace context, and main content area.
  * [ ] Custom navigation module with `useRoute()` hook and `navigate()` function (no external router).
* [ ] Implement global providers:

  * [ ] QueryClientProvider.
  * [ ] ThemeProvider (light/dark, design tokens).
  * [ ] Auth/session provider.
  * [ ] Global error boundary.
* [ ] Establish design tokens (CSS variables) for:

  * [ ] Colors, semantic color roles (success/warn/error/info).
  * [ ] Typography (font families, sizes, line heights).
  * [ ] Spacing, radii, shadows, border widths.
* [ ] Implement initial design-system primitives:

  * [ ] Button, IconButton, Link, Text, Heading.
  * [ ] Input, Textarea, Select, Checkbox, Switch.
  * [ ] Tabs, Dialog, Tooltip, Toast.
  * [ ] Card, PageLayout, PageHeader, EmptyState, Skeleton.

### 3. Run streaming foundation

* [ ] Define `RunStreamState` and `runStreamReducer` around `AdeEvent` (discriminated union for known event types).
* [ ] Implement `RunStreamProvider`:

  * [ ] Holds `RunStreamState` per run.
  * [ ] Manages EventSource to `/runs/{run_id}/events?stream=true&after_sequence=...`.
  * [ ] Handles reconnection, backoff, and teardown.
* [ ] Implement `useRunStream(runId)` hook:

  * [ ] Provides state, derived selectors, and control actions (e.g. pause/resume).
  * [ ] Derived outputs: status, phases, consoleLines, validationSummary, tableSummaries, lastSequence.
* [ ] Implement `createAndStreamRun` and `attachToRun` helpers:

  * [ ] `createAndStreamRun(configId | documentId, options)` — creates a run and wires `RunStreamProvider`.
  * [ ] `attachToRun(runId)` — replays history and continues streaming.
* [ ] Implement `useRunTelemetry(runId)` for historical runs:

  * [ ] Streams `events.ndjson` incrementally using `ReadableStream` + `TextDecoder`.
  * [ ] Feeds events through the same `runStreamReducer` used for live SSE.
* [ ] Implement basic backpressure strategy:

  * [ ] Clamp console buffer to a max number of lines; drop oldest; allow “show all” on demand.
* [ ] Add tests for:

  * [ ] `runStreamReducer`.

### 4. Shared run components & insights

* [ ] Implement `features/runs/components/RunConsole`:

  * [ ] Renders console lines with timestamps, origin (build/run), level, and phase tags.
  * [ ] Filters: origin, level, phase, text search.
  * [ ] “Follow tail” toggle; pause/resume auto-scroll.
  * [ ] “Error-first” mode: jumps to first error event and highlights nearby context.
* [ ] Implement `RunTimeline`:

  * [ ] Linear, compact timeline visualizing build + run phases in order.
  * [ ] Uses durations from `created_at`/`duration_ms`; colors by status (pending/running/succeeded/failed/skipped).
  * [ ] Hover/tooltip showing duration, phase name, key metrics.
* [ ] Implement `RunSummary`:

  * [ ] Status, total duration, start/end timestamps.
  * [ ] Key counts (e.g., rows processed, tables impacted) if available.
* [ ] Implement `ValidationSummary` + per-table cards:

  * [ ] For each table: rows, mapped/unmapped columns, severity indicators.
  * [ ] Overall validation health bar for the run.
  * [ ] Clicking an issue highlights relevant context in the console (when possible).
* [ ] Implement deep-link support:

  * [ ] Given `runId` + `sequence`, replays state up to that event before showing the UI.
  * [ ] Expose a helper to construct deep-linkable URLs (encoded via our custom navigation scheme).

### 5. Run Detail screen (streaming-first)

* [ ] Add route definition for “Run Detail” in the custom router (e.g. `run-detail/:workspaceId/:runId`).
* [ ] Implement `RunDetail` screen:

  * [ ] Layout:

    * Header: run name/id, workspace, status pill, key actions.
    * Left column: RunTimeline + summaries.
    * Right column: RunConsole, with filters and error-first toggle.
  * [ ] Use `useRunStream` for active runs; `useRunTelemetry` for completed runs when loading from history.
  * [ ] Sequence scrubber:

    * Slider that clamps max sequence passed into the reducer.
    * UI label (“Replaying to event N of M”).
  * [ ] Expose actions:

    * Download original file(s) (if run is document-based).
    * Download normalized outputs.
    * Download raw log (NDJSON or text).
  * [ ] Show validation/table summaries in a dedicated “Insights” section.
* [ ] Support deep linking via custom routing:

  * [ ] Route includes `runId` and optional `sequence` param/query.
  * [ ] Opening such a link replays to the target sequence and focuses relevant console line.
* [ ] Ensure “resume after reload” works:

  * [ ] Persist `lastSequence` + run metadata in memory and/or session storage.
  * [ ] On load, detect active run and call `attachToRun(runId)` with correct `after_sequence`.

### 6. Documents & end-user file workflow (primary UX focus)

* [ ] Add route definition for “Documents” (e.g. `documents/:workspaceId`).
* [ ] Implement Documents screen layout:

  * [ ] Left: document list/table with:

    * Name, size, uploaded by, last run status, last run time.
    * Clear status chips (Never run / In progress / Failed / Succeeded).
  * [ ] Right: “Document details” panel for selected document:

    * Tabs: **Overview**, **Runs**, **Outputs**.
    * Overview: file metadata, last run status, quick actions.
    * Runs: run history list with status, duration, config used, created by.
    * Outputs: list of downloadable outputs for the most recent run (or the selected run).
* [ ] Implement upload UX:

  * [ ] Prominent drag-and-drop zone + “Browse files” button.
  * [ ] Show upload progress per file (and any server-side validation errors).
  * [ ] After success:

    * Newly uploaded document appears in the list and becomes selected.
    * Show a “Next step” hint: “Start a run to normalize this file.”
* [ ] Implement “start run” UX from Documents:

  * [ ] Each document shows a “Start run” primary action when no run is active.
  * [ ] If multiple configs are applicable:

    * Inline selection control (dropdown or side panel) to choose config.
  * [ ] After starting a run:

    * The document gets an “In progress” status chip with spinner/progress.
    * The Document details panel shows a **Live Run** card:

      * Summary: phase, progress, elapsed time.
      * Mini console snippet (last N lines).
      * “Open full run view” link (opens Run Detail with streaming).
* [ ] Implement run progress & inspection from Documents:

  * [ ] When a run is active for a document:

    * Use `useRunStream(runId)` in the Live Run card to show current phase + last console lines.
    * Provide a “Show errors” toggle that jumps the snippet to error lines (if any).
  * [ ] When a run completes:

    * Update status chip & card (Succeeded / Failed).
    * Show a “Review results” CTA:

      * For success: “Review normalized outputs”.
      * For failure: “Review errors”.
* [ ] Implement document-centric run history:

  * [ ] Runs tab:

    * List of past runs (most recent first) with status, duration, config name, and user.
    * Each row has:

      * “Open run details” (Run Detail deep link).
      * Status icon and subtle color-coding.
  * [ ] Support quick-run comparison:

    * At minimum: show a small inline diff for row counts/validation severity vs previous run when available.
* [ ] Implement downloads UX:

  * [ ] Outputs tab or section:

    * Separate groups:

      * **Original file** — “Download original”.
      * **Normalized output(s)** — list with format (e.g., CSV/Parquet), size, and description.
      * **Logs** — link(s) to log download (text/NDJSON).
    * Each group has a clear label and icons to avoid confusion.
  * [ ] From Run Detail:

    * Same downloads, but scoped to that specific run.
  * [ ] Ensure that when multiple runs exist, the UI always communicates **which run** an output belongs to (e.g., “Outputs from run #1234”).

### 7. Config Builder migration (Workbench, on top of new foundations)

* [ ] Add route definition for Config Builder (e.g. `config/:workspaceId/:configId`).
* [ ] Rebuild Config Builder screen using:

  * [ ] New layout primitives (PageLayout, PageHeader, sidebars).
  * [ ] New design system controls (inputs, tabs, etc.).
* [ ] Extract `useWorkbenchRun` hook:

  * [ ] Encapsulates:

    * Starting runs for a config.
    * Tracking “current run” metadata.
    * Tying Config Builder to the RunStream foundation (no local EventSource management).
* [ ] Replace local run/validation logic with:

  * [ ] `createAndStreamRun` for starting runs.
  * [ ] `useRunStream` for streaming status/console.
* [ ] Use shared run components:

  * [ ] In the bottom panel, use `RunConsole`, `RunTimeline`, `RunSummary`, `ValidationSummary`.
* [ ] Ensure UX still feels familiar but visually upgraded:

  * [ ] Clear 3-step mental model: **Edit config → Validate → Run and inspect**.

### 8. Global run awareness (v1 + phase 2)

* [ ] Implement minimal “Recent runs” overview:

  * [ ] “Runs” section on Workspace home showing last N runs:

    * Status, duration, source (config vs document), and link to Run Detail.
* [ ] (Phase 2, separate checklist items if/when in scope):

  * [ ] Workspace “live activity” feed.
  * [ ] Active-runs wallboard with cards per active run and live summaries.

### 9. Types, schema, and hygiene

* [ ] Create `schema/` module in the new app:

  * [ ] Re-export selected OpenAPI-generated types via `@schema`.
  * [ ] Add view-model types where API responses are adapted to UI needs.
* [ ] Centralize run-related types in `features/runs/schema`:

  * [ ] `RunResource`, `RunStatus`, `RunStreamEvent`, etc.
  * [ ] `AdeEvent` as a discriminated union for events used in UI.
* [ ] Ensure strict TypeScript:

  * [ ] No implicit `any`.
  * [ ] Strict null checks.
  * [ ] Use exhaustive `switch` on event types where appropriate.

### 10. Testing, accessibility & Definition of Done

* [ ] Unit tests (Vitest):

  * [ ] `runStreamReducer` and selectors.
  * [ ] NDJSON streaming parser.
  * [ ] Console formatting + filters.
* [ ] Integration / E2E tests (Playwright or equivalent):

  * [ ] **Documents flow:**
    Upload file → start run → see live progress → inspect errors/success → download normalized file.
  * [ ] **Run Detail:**
    Open historical run → scrub timeline → deep-link to a specific event → refresh and resume.
  * [ ] **Config Builder:**
    Edit config → run → observe streaming console and summary.
* [ ] Accessibility checks:

  * [ ] Keyboard navigation across Documents, Run Detail, Config Builder.
  * [ ] Focus outlines and skip-to-content where appropriate.
  * [ ] ARIA labels for critical components (upload area, run progress, tabs).
* [ ] Definition of Done:

  * [ ] New ade-web covers all critical flows currently supported by legacy app (Documents + Config Builder).
  * [ ] Run streaming works reliably for both live runs and historical replays.
  * [ ] Documents UX clearly guides users from **upload → run → review → download** with minimal ambiguity.
  * [ ] Legacy app is no longer required in the main deploy pipeline.

---

## 1. Objective

**Goal:**
Rebuild `apps/ade-web` from scratch with a clean, maintainable architecture and a **holistic UX** for:

1. **Configuration authors** in the Config Builder, and
2. **End users** working in the Documents pane who:

   * Upload files,
   * Start runs,
   * Watch progress and debug issues,
   * Download normalized outputs and logs.

We want:

* A **design-forward** application with consistent layout, typography, spacing, and interaction states.
* First-class **event streaming** support that powers run replay, timelines, and rich debugging workflows.
* A composable set of **run-centric UI primitives** used across Config Builder, Documents, and Run Detail.

We are explicitly allowed to:

* Rename/archive the current `apps/ade-web` and build a new app in its place.
* Delete legacy patterns in favor of a standard architecture and consistent UX, even if this means more upfront work.

---

## 2. Context (what we’re starting from)

Today’s `apps/ade-web`:

* Is a Vite + React + TS app with:

  * Routerless navigation and bespoke history helpers.
  * Streaming logic embedded inside Config Builder’s Workbench.
  * Ad-hoc UI primitives and inconsistent visual language.
* Treats streaming as a **local concern**:

  * Workbench manages its own EventSource, reducer, and state.
  * Documents screen only gets basic telemetry snippets, not full streaming power.

We now have:

* A unified `AdeEvent` stream for runs (build + run + logs), with:

  * SSE: `/runs/{run_id}/events?stream=true&after_sequence=0`.
  * Persisted NDJSON: `/runs/{run_id}/events.ndjson`.
* Frontend primitives (or prototypes) such as:

  * `streamRunEvents`, `RunStreamState`, `runStreamReducer`.
  * `fetchRunTelemetry`.

Pain points:

* Documents UX is under-designed:

  * Upload, run start, progress, results, and downloads are not a coherent, guided journey.
* Workbench is a **mega-component** blending layout, editing, streaming, and persistence logic.
* Telemetry loading can freeze the UI on large runs.
* There is no single, composable **Run Experience** that can be reused in multiple contexts.

---

## 3. Target architecture / structure

We retain Vite + React + TypeScript, but rebuild the app with a clear layering and a small, well-typed navigation module (instead of an external router).

```text
apps/ade-web/
  src/
    app/
      AppShell.tsx          # Top-level layout and providers
      navigation/           # Custom "vanilla React" routing
        routes.ts           # Route definitions (typed)
        useRoute.ts         # Hook that returns current route
        navigate.ts         # Programmatic navigation API
    routes/                 # Route-level screens, thin composition
      WorkspaceHome/
      Documents/
      RunDetail/
      ConfigBuilder/
    features/
      runs/
        api/                # Run API clients (start run, fetch summaries, etc.)
        stream/             # RunStreamProvider, hooks, reducer, selectors
        components/         # RunConsole, RunTimeline, RunSummary, ValidationSummary
        schema/             # Run-related types shared with UI
      documents/
        api/
        components/         # DocumentList, UploadPanel, DocumentDetails, etc.
      configs/
        api/
        components/
      auth/
        api/
        hooks/
    ui/                     # Design system primitives
      Button.tsx
      Input.tsx
      Tabs.tsx
      Dialog.tsx
      ...
    shared/                 # Cross-cutting (env, storage, formatting, hooks)
    schema/                 # Curated OpenAPI exports via @schema
    test/                   # Testing setup & helpers
```

**Navigation (custom, vanilla React):**

* `routes.ts` defines a small set of route descriptors, e.g.:

  ```ts
  type Route =
    | { kind: 'workspaceHome'; workspaceId: string }
    | { kind: 'documents'; workspaceId: string }
    | { kind: 'runDetail'; workspaceId: string; runId: string; sequence?: number }
    | { kind: 'configBuilder'; workspaceId: string; configId: string };
  ```

* `useRoute()`:

  * Parses `window.location` into a `Route`.
  * Subscribes to `popstate` to react to back/forward.

* `navigate(route: Route)`:

  * Serializes the `Route` to a URL.
  * Calls `history.pushState` and triggers re-render.

This gives us URL-based navigation, deep links, and browser back/forward, but keeps us in “vanilla React” with a small, well-scoped routing module.

---

## 4. UX & design

### 4.1 Design principles

* **Guided, end-to-end flows:**
  Especially for Documents, users should always see the “next step”:

  * After upload → “Start a run”.
  * During run → “Review progress”.
  * On completion → “Download outputs” or “Review errors”.

* **Calm, legible information hierarchy:**

  * Clear page headers with context (workspace, document, run).
  * Primary actions are obvious, secondary actions subdued.
  * Status chips and colors are consistent across screens.

* **Consistency across screens:**

  * Shared components for run console, timelines, and summaries.
  * Common layout patterns (PageHeader + content + side panels).

* **Streaming-aware design:**

  * Live updates feel smooth, not noisy.
  * Users can switch between “live tail” and “investigate past events” (with scrubbers and filters).

### 4.2 Key flows

#### A. Documents: Upload → Run → Review → Download

**User story:**
“As an end user, I upload a file, start a run, watch how it progresses, understand errors quickly if it fails, and download the normalized outputs and logs when it succeeds.”

**UX shape:**

* **Documents list (left column):**

  * Table with:

    * Name, size, uploaded by, last run status, last run time.
  * Status chips:

    * Grey: Never run.
    * Blue: In progress.
    * Green: Succeeded.
    * Red: Failed.

* **Document details (right panel):**

  * Persistently visible for the selected document.
  * Tabs:

    * **Overview:** Summary tile (status, last run, quick actions).
    * **Runs:** History list (see run trajectories).
    * **Outputs:** Downloadable artifacts for the selected or latest run.

* **Upload panel:**

  * Big drag & drop zone plus “Browse files” button.
  * Shows per-file upload progress and errors inline.
  * After upload, automatically selects the new document and reveals a “Start run” call to action.

* **Start run panel:**

  * Inline in the details panel:

    * If only one config is applicable, show a single “Start run” button.
    * If multiple, show a small config selector, then “Start run”.
  * Provide a short, human description:

    * “Run with config X to normalize into Y schema.”

* **Live Run card (for active run):**

  * When a run is in progress:

    * Status chip and phase (“Normalizing”, “Validating”).
    * Time elapsed.
    * Mini timeline bar (basic phase progression).
    * Mini console snippet (last N lines).
    * “Open full run view” link to the Run Detail screen.
  * Error-first toggle:

    * When errors appear, a small badge:

      * “Errors detected – View errors”
    * Clicking focuses console snippet around the first error.

* **Run history:**

  * Runs tab shows:

    * List of runs with status icon, duration, config, and created time/user.
    * Quick visual indicator for regression vs previous run (e.g., more severe validation level).

* **Outputs:**

  * Clearly separated sections:

    * Original file.
    * Normalized outputs (possibly multiple formats).
    * Logs.
  * Each item:

    * Label, file type, size, last updated time.
    * Download button with a consistent icon.
  * Always communicates which run you’re looking at (“Outputs from run #1234”).

#### B. Run Detail: Inspection, replay, and debugging

**User story:**
“As anyone investigating an issue, I open a run, scrub through its events, quickly find where it failed, and cross-reference validation issues with console logs and phase timelines.”

**UX shape:**

* Page header:

  * Run title or ID, workspace, created by, creation time.
  * Status pill (Queued / Running / Succeeded / Failed / Cancelled).
  * Key actions:

    * Download artifacts (normalized output, logs).
    * Copy link to this run (deep link).
* Main layout:

  * Left side:

    * RunSummary (status, duration, high-level metrics).
    * RunTimeline (build + run phases in order).
    * ValidationSummary (overall health).
  * Right side:

    * RunConsole with:

      * Filters (origin/level/phase/text).
      * Follow tail toggle.
      * Error-first toggle and navigation between errors.
* Sequence scrubber:

  * Slider or timeline bar to “replay” from start to sequence N.
  * Indicator text (“Replaying up to event 132/600”).
* Deep links:

  * “Copy link to this error” from console:

    * Generates a URL embedding `runId` + `sequence`.
  * Opening the link:

    * Replays events up to that sequence and centers the console on that event.

#### C. Config Builder: Authoring & streaming feedback

We keep the existing mental model but align visuals and streaming behavior with the new system:

* Clear structure:

  * Left: config tree/navigation.
  * Center: editor/form views.
  * Bottom: Run panel using shared components (timeline, console, summaries).
* Runs are started via `useWorkbenchRun` which calls `createAndStreamRun` under the hood.
* Validations and runs share the same streaming mechanics for console + summaries.

#### D. Workspace: Orientation & recent activity

* Workspace home:

  * Overview cards:

    * “Documents” summary (count, recent uploads).
    * “Recent runs” list (no streaming required in v1).
  * Each recent run links to Run Detail.

---

## 5. Streaming & data design

* **Unified run state:**

  * `RunStreamState` represents:

    * Raw events, derived phases, console lines, validation and table summaries, status, last sequence.
* **SSE & NDJSON:**

  * For active runs:

    * Use EventSource from `streamRunEvents`.
  * For historical runs:

    * Use `fetchRunTelemetry` wrapped in a streaming parser and feed into the same reducer.
* **Backpressure:**

  * Maintain capped buffers for console lines by default.
  * Allow user to “Load more history” or “View full log” if needed.
* **Resilience:**

  * On network hiccups:

    * Reconnect automatically with `after_sequence = lastSequence`.
    * Indicate reconnection state subtly in the UI (icon/spinner, not a disruptive modal).

---

## 6. Implementation plan / phases

You can adapt this, but a reasonable sequence:

1. **Phase 0 – Archive & scaffold**

   * Archive existing app, scaffold new Vite+React+TS app.
   * Set up navigation module, providers, and basic design system.

2. **Phase 1 – Run streaming foundation**

   * Implement RunStream reducer, provider, hooks, and NDJSON parser.
   * Add basic tests.

3. **Phase 2 – Shared run components**

   * Build RunConsole, RunTimeline, RunSummary, ValidationSummary.
   * Wire them up with RunStream state.

4. **Phase 3 – Run Detail screen**

   * Implement the Run Detail route using shared components.
   * Add replay and deep-link support.

5. **Phase 4 – Documents experience**

   * Build Documents list, upload UX, document details, run history, and outputs.
   * Integrate streaming Run cards for active runs.

6. **Phase 5 – Config Builder migration**

   * Rebuild Config Builder on top of new design system and streaming foundation.
   * Remove legacy streaming logic.

7. **Phase 6 – Polish & cutover**

   * UX polish, accessibility, and E2E tests.
   * Decide on timeline to stop exposing the legacy app.

---

## 7. Definition of Done (for this workpackage)

This workpackage is considered complete when:

1. **Architecture & routing**

   * New `apps/ade-web` uses the custom navigation module (no external router).
   * All primary flows are reachable via URL and support browser back/forward.

2. **Streaming foundation**

   * `RunStreamProvider` and `useRunStream` are the single way to stream run events.
   * Both live and historical runs use the same state/reducer.
   * Large runs are manageable (no UI freezes due to full NDJSON loads).

3. **UX for Documents**

   * A user can:

     * Upload file(s).
     * Start a run from a document.
     * Observe live progress with clear status and phase feedback.
     * Investigate failures via error-first views.
     * Download original, normalized outputs, and logs, always knowing which run they belong to.
   * The flow feels cohesive and self-explanatory.

4. **Run Detail & Config Builder**

   * Run Detail provides replay, timeline, console with filters, and download actions.
   * Config Builder uses shared run components and the RunStream foundation (no ad-hoc streaming).

5. **Quality**

   * Unit tests pass for streaming primitives and formatting.
   * E2E tests pass for key flows in Documents, Run Detail, and Config Builder.
   * Basic accessibility checks pass (keyboard nav, focus, ARIA on key components).

6. **Legacy**

   * Legacy app is kept only as `apps/ade-web-legacy` and is not relied on for primary workflows or deploys.
