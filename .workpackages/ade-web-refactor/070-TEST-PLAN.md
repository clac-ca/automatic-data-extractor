# ADE Web – Test & Quality Plan

> This document defines how we test the new `apps/ade-web` implementation described in  
> `010-WORK-PACKAGE.md` and related specs (`020-ARCHITECTURE.md`, `030-UX-FLOWS.md`, `050-RUN-STREAMING-SPEC.md`, `060-NAVIGATION.md`).

---

## 1. Purpose & Goals

We’re rebuilding `apps/ade-web` from scratch, with:

- A new architecture and navigation layer,
- A new design system,
- A central run-streaming foundation,
- A much richer Documents + Run Detail UX.

This test plan ensures:

- Critical flows (especially **Documents upload → run → review → download**) are reliable.
- Run streaming (SSE + NDJSON) is correct and resilient.
- Navigation, deep-linking, and replay behave as specified.
- We maintain a baseline of accessibility and performance.

This plan is **in scope for this workpackage** and must be satisfied before considering the refactor complete.

---

## 2. Scope

### 2.1 In-scope features

- **Navigation & routing**
  - Custom history-based navigation (no React Router).
  - URL parsing and deep-link handling.

- **Run streaming & telemetry**
  - `RunStreamState` and `runStreamReducer`.
  - `RunStreamProvider`, `useRunStream`, `useRunTelemetry`.
  - SSE attach/reconnect; NDJSON replay.

- **Run UI primitives**
  - `RunConsole` (filters, follow-tail, error-first).
  - `RunTimeline`.
  - `RunSummaryPanel`, `ValidationSummary`.

- **Screens & flows**
  - Workspace Home.
  - Documents screen (upload, run, progress, outputs).
  - Run Detail screen (inspect, replay, deep-link).
  - Config Builder screen (run panel, shared components).

- **Design system primitives**
  - Buttons, inputs, tabs, dialog, toast, status badges.

### 2.2 Out-of-scope (for this workpackage)

We don’t need full test coverage for later-phase “nice-to-haves” like:

- Workspace live activity feed.
- Active-runs wallboard.
- Cross-run comparison views.

The architecture should support testing them when they are introduced, but they are not required to satisfy this plan.

---

## 3. Test Types & Tools

We use:

- **Vitest + React Testing Library** for unit and integration tests.
- **Playwright (or similar)** for end-to-end tests.
- **ESLint + TypeScript strict** for static checks.
- Optional **pa11y / axe** for accessibility checks in CI (or equivalent).

### 3.1 Unit Tests

Target:

- Pure logic (reducers, selectors, utilities).
- Hooks with minimal external dependencies (mocked API/stream).

Examples:

- `runStreamReducer` handling sequences, phases, errors.
- URL → Route parsing and Route → URL serialization.
- NDJSON parsing utilities.

### 3.2 Component / Integration Tests (DOM-level)

Target:

- Components in isolation or with a light provider wrapper.
- Hooks interacting with real DOM state (e.g. filtering console, tab switching).

Examples:

- `RunConsole` filters.
- `RunTimeline` rendering of phases.
- `DocumentList` rendering statuses and actions.

### 3.3 End-to-End Tests (E2E)

Target:

- Critical user journeys across multiple screens and features.

Examples:

- Documents: upload → start run → watch progress → download outputs.
- Run Detail: open from Documents, scrub timeline, replay via deep link.
- Config Builder: edit config → run → debug failed run.

---

## 4. Test Coverage by Area

### 4.1 Navigation & Routing

**Goal:** Ensure custom navigation is robust and correctly mapped to URLs.

**Unit/Integration:**

- `parseLocation`:
  - Given URL patterns, returns expected `Route` values.
  - Handles missing or malformed params gracefully.
- `buildUrl`:
  - Given `Route`, produces canonical URLs.
- `useNavigation`:
  - `navigate()` updates `route` and `window.location`.
  - `popstate` updates `route` without extra pushes.

**E2E:**

- Direct navigation to:
  - `/workspaces/:workspaceId/documents` → Documents screen.
  - `/workspaces/:workspaceId/runs/:runId` → Run Detail screen.
  - `/workspaces/:workspaceId/configs/:configId` → Config Builder.
- Browser Back/Forward:
  - Navigate Documents → Run Detail → Documents, Back returns to previous screen with preserved basic state (when reasonable).

---

### 4.2 Design System & UI Primitives

**Goal:** Avoid regressions in base components and ensure accessible, consistent behavior.

**Unit/Integration:**

- `Button`:
  - Click events fired correctly.
  - Disabled and loading states respected (no double-click).
- `Input`/`Select`:
  - Label association and error messages.
- `Tabs`:
  - Only one tab panel visible at a time.
  - Keyboard navigation between tabs.
- `Dialog`:
  - Modal focus trapping.
  - Close on Esc.

We don’t need exhaustive visual tests; key behavior tests are sufficient.

---

### 4.3 Run Streaming & Telemetry

**Goal:** `RunStreamState` and its hooks behave correctly in both live and historical contexts.

**Unit:**

- `runStreamReducer`:
  - Applies a sequence of events in order; `lastSequence` always matches latest event.
  - Correctly derives:
    - Phases (start/end, statuses).
    - Console lines (merged from log events).
    - Validation summaries and per-table summaries.
  - Handles:
    - Mixed build/run events.
    - Errors (populates `errorEvents` and marks status appropriately).
    - Completion events (transition to `completed`).

- Selector functions:
  - `selectCurrentPhase`, `selectConsoleLines`, `selectFirstError`, etc.

**Integration:**

- `useRunStream`:
  - Attaches an SSE connection on mount (mocked EventSource).
  - Dispatches events into reducer in batches.
  - Reconnects after simulated errors using `after_sequence = lastSequence`.
  - Cleans up EventSource on unmount.

- `useRunTelemetry`:
  - Given NDJSON mock stream:
    - Reads line-by-line.
    - Dispatches events until EOF.
    - Marks run `completed` at end.
  - When given an `upToSequence`:
    - Stops feeding events once that sequence is reached.

**Edge cases:**

- Out-of-order or duplicate sequence numbers are at least surfaced (log/warn).  
  We can decide whether to strictly enforce ordering or be defensive.

---

### 4.4 Run UI Components

**Goal:** Shared run components behave correctly with realistic run states.

**Integration:**

- `RunConsole`:
  - Renders lines with level, origin, message.
  - Filtering:
    - Text search filters by message.
    - Level filter hides non-matching levels.
    - Build vs run filter works.
  - “Follow tail”:
    - When enabled, scrolls to bottom as new lines arrive.
    - When disabled, keeps scroll position.
  - Error-first behavior:
    - On “Show errors” or similar trigger, scrolls to first error and highlights it.

- `RunTimeline`:
  - Given a list of phases, displays them in order.
  - Status coloring matches spec (queued/running/succeeded/failed).
  - Duration labels or tooltips show correct values.

- `RunSummaryPanel`:
  - Displays status, duration, error count, table summaries.
  - For a failing run, clearly highlights the failure.

---

### 4.5 Documents Screen & Flow

**Goal:** High confidence in the core end-user flow.

**Unit/Integration:**

- `DocumentList`:
  - Renders name, status, last run info.
  - Shows correct status badges based on props.
- `UploadPanel`:
  - Shows progress for mock uploads.
  - Renders error states properly.
- `DocumentDetail` (without streaming):
  - Overview tab renders file info and last run summary.
  - Runs tab lists runs; clicking a run calls callback or shows detail.
  - Outputs tab lists downloadable artifacts with appropriate labels.

**E2E (happy path):**

1. **Upload → Run → Outputs**
   - Navigate to Documents.
   - Upload a file (using test fixture).
   - See the new document appear with “Never run”.
   - Click “Start run”:
     - Status changes to “Running”.
     - Live run card shows phase and log snippet.
   - When the backend fixture completes:
     - Status → “Succeeded”.
     - Outputs tab shows normalized file; download button enabled.

2. **Failed Run → Error Discovery**
   - Use fixture that causes the run to fail.
   - Verify:
     - Status → “Failed”.
     - Live run card or detail highlights failure.
     - Clicking “View errors” opens Run Detail or expanded console area focusing on error.

---

### 4.6 Run Detail Screen & Replay

**Integration:**

- `RunDetailScreen` with mocked `useRunTelemetry` and `useRunStream`:
  - Renders run summary, timeline, console, and outputs panel.
  - When given `sequence` param:
    - Renders replay state up to that sequence.
    - Console centered near that sequence.

**E2E:**

1. **Open historical run via URL**
   - Navigate directly to `/workspaces/:workspaceId/runs/:runId`.
   - See final state (completed) and full console.

2. **Replay**
   - Use slider to move to mid-sequence.
   - Console and timeline reflect partial state.
   - “Return to live” (or full) shows final state again.

3. **Deep link to error**
   - From a failing run, copy “link to this error” (includes `sequence`).
   - Open link in fresh browser context.
   - Page loads with console focused around that error.

---

### 4.7 Config Builder Screen

**Integration:**

- `ConfigBuilderScreen` + `useWorkbenchRun`:
  - Starting a run calls `useRunStream` / `useCreateAndStreamRun` under the hood.
  - Run panel updates as events arrive.
  - Validation tab shows summary and per-table info if available.

**E2E:**

1. **Run from Config Builder**
   - Navigate to a config.
   - Trigger a run.
   - See run panel timeline & console updating.
   - On success, see completion and link to Run Detail.

2. **Failure in configuration**
   - Use failing fixture.
   - Ensure:
     - Error-first view is triggered in run panel.
     - Config sections related to error are highlighted or referenced (if implemented in this workpackage).

---

### 4.8 Workspace Home

**Integration:**

- `WorkspaceScreen`:
  - Shows recent documents and runs.
  - Clicking tiles navigates correctly (Documents, Config Builder, Run Detail).

We don’t need heavy tests here; just basic rendering and navigation.

---

## 5. Test Data & Fixtures

To keep tests stable:

- Use **fixture runs** with deterministic AdeEvent sequences:
  - Simple success run.
  - Simple failure run (error in mapping/validation).
  - Large-ish run (hundreds/thousands of events) for buffer tests.
- Use **fixture documents** and **configs** with stable IDs and metadata.
- Mock SSE with a small wrapper that:
  - Feeds events at controlled intervals.
  - Simulates network failures in some tests.

For E2E, either:

- Point to a test backend seeded with known fixtures, or
- Use a test mode where the app hits a mock server (e.g. MSW) that reproduces SSE/NDJSON behavior.

---

## 6. Testing Workflow & CI

### 6.1 Local Development

- Run unit/integration tests:
  - `pnpm test:unit` (or equivalent).
- Run E2E tests:
  - `pnpm test:e2e` against a local or ephemeral environment.

### 6.2 CI Pipeline

- **Phase 1 – Static checks**
  - TypeScript compile.
  - ESLint.

- **Phase 2 – Unit / Integration**
  - Vitest test suite (with coverage threshold on `features/runs`, `features/documents`, `screens`).

- **Phase 3 – E2E (selected flows)**
  - At least the 3 key journeys:
    - Documents: upload → run → download.
    - Run Detail: replay & deep link.
    - Config Builder: run & inspect.

A change that breaks these tests should block merging.

---

## 7. Quality Gates & Exit Criteria

This workpackage’s refactor is considered **test-complete** when:

1. **All unit/integration tests pass**, covering:
   - `runStreamReducer` and critical selectors.
   - `useRunStream` / `useRunTelemetry`.
   - Core UI primitives and key feature components.

2. **All E2E flows pass:**
   - At least:
     - Documents upload → run → outputs (success path).
     - Documents run failure → error inspection.
     - Run Detail replay and error deep link.
     - Config Builder run → log streaming.

3. **Accessibility checklist:**
   - Documents screen, Run Detail, and Config Builder:
     - Navigable by keyboard.
     - Basic ARIA roles and labels set for tabs, dialogs, and status indicators.
   - A lightweight automated a11y scan (axe or similar) shows no critical issues.

4. **No known critical bugs** in:
   - Run streaming (no consistent missed events, crashes, or stuck states).
   - Documents upload and run flows.
   - Downloads (no broken links for expected artifacts).

5. **Legacy dependence removed**:
   - New app’s tests and flows run independently of `apps/ade-web-legacy`.
   - CI no longer depends on legacy app to validate new changes.

Once these criteria are met—and manual exploratory testing doesn’t reveal blocking issues—the test plan for this workpackage is satisfied.