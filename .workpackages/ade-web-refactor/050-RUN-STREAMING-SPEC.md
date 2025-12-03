# ADE Web – Run Streaming Spec  
`.workpackages/ade-web-refactor/050-RUN-STREAMING-SPEC.md`

> This document is the **source of truth** for how the new ade‑web frontend consumes run events (live SSE and historical NDJSON), how state is modeled, and how screens (Documents, Run Detail, Config Builder) should interact with the streaming layer.
>
> If you need to change streaming behavior, **update this spec first**, then the code.

---

## 1. Scope & Goals

### 1.1 What this spec covers

- How we consume **run events** from ADE:
  - Live via **SSE** (`/runs/{run_id}/events?stream=true&after_sequence=…`).
  - Historical via **NDJSON** (`/runs/{run_id}/events.ndjson`).
- The shared **RunStreamState** and reducer.
- The public **hooks & provider APIs**:
  - `useRunStream(runId)`
  - `useRunTelemetry(runId, options?)`
- Behavior for:
  - Live streaming.
  - Replay & scrubbing.
  - Deep links (run_id + sequence).
  - Error handling & reconnection.
  - Backpressure and performance.

### 1.2 Goals

- **Single foundation**: All screens use the same streaming logic and state (Documents, Run Detail, Config Builder, future dashboards).
- **UX-aligned**:
  - Live progress & console tail.
  - Error-first debugging.
  - Replay to any event (within buffered history).
  - “Resume after reload” for active runs.
- **Robust**:
  - Handles dropped connections & retries gracefully.
  - Scales to large runs without freezing the UI.
- **Typed & testable**:
  - Strong TypeScript types for events and state.
  - Reducer and hooks are unit-testable in isolation.

### 1.3 Out of scope

- Backend event format details beyond what the frontend needs.
- Visualization details (colors, layout) – see `040-DESIGN-SYSTEM.md` and `030-UX-FLOWS.md`.
- Run comparison / cross-run analytics (future work).

---

## 2. Concepts & Terms

- **Run** – A single execution of a build/run pipeline (possibly tied to a config or a document).
- **AdeEvent** – Backend event envelope for run/build/log events; each event:
  - Belongs to a specific `run_id`.
  - Has a monotonically increasing `sequence` integer within that run.
  - Has at least `type`, `created_at`, and `payload`.

- **SSE stream** – Live stream of AdeEvents:
  - `GET /runs/{run_id}/events?stream=true&after_sequence={seq}`.

- **NDJSON telemetry** – Historical event log for a run:
  - `GET /runs/{run_id}/events.ndjson`.
  - Each line = one AdeEvent (JSON).

- **RunStreamState** – In-memory state for a run’s stream as used by the frontend:
  - Stores recent events and derived slices (console lines, phases, validation summaries, etc.).

- **View sequence** – For replay:
  - The sequence up to which we consider events “applied” for UI (e.g., slider position).
  - May be ≤ `lastSequence` (we keep full history but only apply up to viewSequence when replaying).

---

## 3. Data Sources & Assumptions

### 3.1 SSE endpoint

- Endpoint:  
  `GET /runs/{run_id}/events?stream=true&after_sequence={sequence}`

**Assumptions:**

- Events are delivered in **ascending sequence** order.
- `after_sequence = 0` starts from the first event.
- Reconnecting with `after_sequence = N` will deliver **events with sequence > N** only.
- SSE stream closes once run reaches a terminal status (`succeeded`, `failed`, `canceled`) and all events have been sent.

### 3.2 NDJSON endpoint

- Endpoint:  
  `GET /runs/{run_id}/events.ndjson`

**Assumptions:**

- Events are written in ascending sequence order.
- File content is immutable for a completed run.
- File can be large – we must use streaming parsing.

### 3.3 AdeEvent (frontend view)

We don’t need every field typed, but we require a minimal shape:

```ts
interface BaseAdeEvent {
  run_id: string;
  sequence: number;
  created_at: string; // ISO string
  type: string;       // e.g. "run.started", "run.phase.completed", "log.line"
  payload: unknown;   // typed via discriminated unions where we care
}
````

Where we have stable event types (e.g. `run.started`, `run.completed`, `log.line`, `validation.summary`, `table.summary`), we define discriminated unions on top of this base type so the UI can be precise and safe.

---

## 4. Core State Model

### 4.1 RunStreamStatus

```ts
type RunStreamStatus =
  | 'idle'        // no data yet
  | 'attaching'   // establishing SSE or starting NDJSON replay
  | 'live'        // attached to SSE and applying events as they arrive
  | 'replaying'   // reading NDJSON and applying events up to a target sequence
  | 'paused'      // stream detached but state retained (e.g., user navigated away)
  | 'completed'   // run terminal; full final state known
  | 'error';      // unrecoverable streaming error
```

### 4.2 Derived types (examples)

We derive several UI-level structures from events:

```ts
interface ConsoleLine {
  sequence: number;
  timestamp: string;
  level: 'debug' | 'info' | 'warn' | 'error';
  origin: 'build' | 'run' | 'system';
  phase?: string;       // e.g. "mapping", "validation"
  message: string;
  jsonPayload?: unknown; // for structured inspection
}

type PhaseStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'skipped';

interface PhaseState {
  key: string;          // unique per phase (e.g. "build:compile", "run:mapping")
  name: string;
  kind: 'build' | 'run';
  status: PhaseStatus;
  startedAt?: string;
  completedAt?: string;
  durationMs?: number;
}

interface ValidationSummary {
  overallSeverity: 'ok' | 'warning' | 'error';
  totalIssues: number;
  tables: TableSummary[];
}

interface TableSummary {
  tableName: string;
  rowCount?: number;
  mappedColumns?: number;
  unmappedColumns?: number;
  severity: 'ok' | 'warning' | 'error';
  issueCount?: number;
  // Optionally: a reference to a sequence or set of sequences where issues surfaced
  representativeSequence?: number;
}
```

### 4.3 RunStreamState

```ts
interface RunStreamState {
  runId: string | null;
  status: RunStreamStatus;
  // Sequence bookkeeping
  lastSequence: number;     // highest sequence we've seen
  viewSequence: number;     // up to where we "apply" state (for replay/scrub)
  // Raw event buffer (capped)
  events: BaseAdeEvent[];   // or AdeEvent union
  // Derived slices
  consoleLines: ConsoleLine[];
  phases: PhaseState[];
  validationSummary: ValidationSummary | null;
  tableSummaries: TableSummary[];
  // Errors / status
  terminalStatus?: 'succeeded' | 'failed' | 'canceled';
  errorEvents: BaseAdeEvent[];
  firstErrorSequence?: number;
  errorMessage?: string;    // streaming-level error (not run-level)
}
```

**Notes:**

* `events` holds up to a configured max (see backpressure). This is the authoritative source for replay within the buffered window.
* `viewSequence` enables “scrubbing” by applying only events with `sequence <= viewSequence` when we derive `consoleLines`, `phases`, etc.

---

## 5. Reducer & Actions

### 5.1 Principles

* **Pure**: No side effects, only state → state transitions.
* **Monotonic**: Never decrease `lastSequence`.
* **Order-safe**: If events arrive out of order (should be rare), we ignore stale ones.

### 5.2 Actions (high-level)

```ts
type RunStreamAction =
  | { type: 'ATTACH_START'; runId: string }
  | { type: 'ATTACH_SUCCESS'; runId: string }
  | { type: 'ATTACH_ERROR'; runId: string; error: string }
  | { type: 'EVENTS_RECEIVED'; runId: string; events: BaseAdeEvent[] }
  | { type: 'SET_VIEW_SEQUENCE'; runId: string; viewSequence: number }
  | { type: 'MARK_TERMINAL'; runId: string; status: 'succeeded' | 'failed' | 'canceled' }
  | { type: 'RESET'; runId: string };
```

Internally, we may break `EVENTS_RECEIVED` into more granular actions, but the external interface doesn’t need to expose them.

### 5.3 EVENTS_RECEIVED behavior

For each event in sequence order:

1. Ignore if `event.sequence <= state.lastSequence` (already applied).
2. Append to `events` buffer (subject to cap).
3. Update:

   * `lastSequence`.
   * `consoleLines` (for log-like events).
   * `phases` (for phase start/complete events).
   * `validationSummary` / `tableSummaries` (for summary events).
   * `errorEvents` and `firstErrorSequence` if this is an error-type event.
4. If `viewSequence` is **not explicitly set** (meaning we’re in “live” mode), keep `viewSequence` in sync with `lastSequence`.

### 5.4 SET_VIEW_SEQUENCE behavior

* Clamp `viewSequence` to `[0, lastSequence]`.
* Re-derive derived slices (console, phases, validation) based on events `sequence <= viewSequence`.
* Used by replay slider and deep link initial loads.

---

## 6. Providers & Hooks

We use a **single** `RunStreamProvider` at app level as a registry for **multiple** runs, then hooks to attach to specific `runId`s.

### 6.1 RunStreamProvider (root)

* Mounted in `AppShell`.
* Holds:

  * A map `runId -> RunStreamState`.
  * SSE connections per `runId` (managed internally).
* Exposes internal context with:

  * `getState(runId)`.
  * `dispatch(runId, action)`.
  * `ensureLiveStream(runId, options)`.
  * `stopLiveStream(runId)`.

The rest of the app never interacts with `EventSource` directly.

### 6.2 useRunStream(runId)

Public hook used by screens/components.

**Signature (conceptual):**

```ts
interface UseRunStreamOptions {
  // If true, automatically attach a live SSE stream when hook is used.
  attachLive?: boolean;
  // If true, do not auto-attach if run is known terminal.
  skipIfCompleted?: boolean;
}

function useRunStream(runId: string, options?: UseRunStreamOptions): {
  state: RunStreamState;
  status: RunStreamStatus;
  lastSequence: number;
  viewSequence: number;
  consoleLines: ConsoleLine[];
  phases: PhaseState[];
  validationSummary: ValidationSummary | null;
  tableSummaries: TableSummary[];
  firstErrorSequence?: number;
  terminalStatus?: 'succeeded' | 'failed' | 'canceled';
  attachLive: () => void;
  detachLive: () => void;
  setViewSequence: (viewSequence: number) => void; // used by replay slider
  goLive: () => void; // sets viewSequence = lastSequence and attaches live SSE
};
```

**Usage examples:**

* **Documents live run card**:

  * `useRunStream(runId, { attachLive: true })`.
* **Run Detail for active run**:

  * Attach live SSE on mount; if route includes `sequence`, call `setViewSequence(sequence)` for replay.
* **Config Builder**:

  * `useWorkbenchRun` uses `useRunStream` to show run panel.

### 6.3 useRunTelemetry(runId, options?)

Public hook for historical replay via NDJSON.

**Signature (conceptual):**

```ts
interface UseRunTelemetryOptions {
  upToSequence?: number;   // stop after this sequence for deep links/replay
  autoStart?: boolean;     // if true, start on mount
}

function useRunTelemetry(
  runId: string,
  options?: UseRunTelemetryOptions
): {
  status: 'idle' | 'loading' | 'loaded' | 'error';
  error?: string;
  startReplay: (overrideOpts?: UseRunTelemetryOptions) => void;
};
```

**Behavior:**

* When started:

  * Dispatch `ATTACH_START` with `status = 'replaying'`.
  * Fetch NDJSON via streaming reader.
  * Parse line-by-line and dispatch `EVENTS_RECEIVED` with batches.
* Completion:

  * When NDJSON ends:

    * Set `viewSequence` to `min(upToSequence ?? lastSequence, lastSequence)`.
    * Optionally mark status as `completed` if we see a terminal run event.
* If the run is still active:

  * Screens can call `useRunStream(runId, { attachLive: true })` after NDJSON to switch to live tail with `after_sequence = lastSequence`.

**Usage examples:**

* **Run Detail (historical run)**:

  * On initial load, call `useRunTelemetry(runId, { autoStart: true })`.
* **Deep link with `?sequence=123`**:

  * Call `useRunTelemetry(runId, { autoStart: true, upToSequence: 123 })`.
  * Once loaded, the UI can also offer a “Go live” button which calls `goLive()` and attaches SSE.

---

## 7. Backpressure & Performance

### 7.1 Event & console buffer caps

To avoid unbounded memory growth:

* `events` buffer:

  * Cap at `MAX_EVENTS` (e.g. ~10,000 events per run).
  * If buffer is full when we append new events:

    * Drop the oldest events (e.g. via ring buffer or slice).
* `consoleLines`:

  * Cap at `MAX_CONSOLE_LINES` (e.g. ~5,000 lines).
  * Drop oldest lines as new ones arrive.

**Implication for replay:**

* Replay slider and deep links can only go as far back as the earliest buffered sequence.
* If user attempts to scrub before that:

  * We clamp `viewSequence` to the earliest available sequence.
  * UI should communicate limitation (e.g. “Older events not available in this view; download full logs instead”).

### 7.2 Batch dispatching

* Accumulate incoming SSE events in a local buffer and dispatch as a batch:

  * E.g. dispatch once per animation frame or small time window.
* NDJSON replay already deals in batches (lines per chunk).

This keeps React updates efficient and avoids re-rendering per event.

### 7.3 Virtualization (future)

Not required for this workpackage, but the console UI should be structured so that we can introduce virtualization (windowed list) later without changing streaming APIs.

---

## 8. Error Handling & Resilience

### 8.1 SSE errors & reconnect

* If SSE connection closes unexpectedly (network issue, timeout):

  * Mark stream as having a **transient error** but attempt reconnect with exponential backoff.
  * Use `after_sequence = lastSequence` when reconnecting.
* Reconnect policy:

  * A handful of attempts (e.g. 3–5) with backoff.
  * After that, set `status = 'error'` and surface an explicit “Retry live connection” action in the UI.

### 8.2 NDJSON errors

* If NDJSON fetch fails:

  * Set `status = 'error'` for telemetry.
  * Preserve existing state (if any).
* If a particular line is invalid JSON:

  * Skip that line and log (dev console); do **not** error the whole replay.
* For unrecoverable parsing failures:

  * Surface a user-facing message in Run Detail (“Could not fully load logs; please download raw logs”).

### 8.3 Run vs stream errors

* **Stream errors** (SSE/NDJSON) affect `RunStreamStatus` but do not change `terminalStatus`.
* **Run errors** (e.g. `run.failed`) update:

  * `terminalStatus = 'failed'`.
  * `firstErrorSequence` if not set.
* UI must differentiate:

  * “Run failed” vs “We’re unable to stream updates right now.”

---

## 9. Deep Linking, Replay & “Resume after reload”

### 9.1 Deep link format

* Run Detail URL:

  * `/workspaces/{workspaceId}/runs/{runId}`
  * Optional `sequence` query param:

    * `/workspaces/{workspaceId}/runs/{runId}?sequence=123`

### 9.2 Opening a deep link

1. Parse URL; extract `runId` and `sequence?`.
2. Use `useRunTelemetry(runId, { autoStart: true, upToSequence: sequence })`.
3. When replay completes:

   * `viewSequence = sequence` (or `lastSequence` if smaller).
   * Console scrolls to that event.
4. If run is not terminal:

   * Offer “Go live” button that:

     * Sets `viewSequence = lastSequence`.
     * Attaches SSE stream with `after_sequence = lastSequence`.

### 9.3 “Resume after reload” for active runs

**Goal:** If user reloads Config Builder or Run Detail mid-run, we resume streaming from where we left off instead of reloading everything.

Approach:

* Optional (and small) persistence mechanism, e.g. `sessionStorage`:

  * For each active `runId`, store:

    * `lastSequence`.
    * `lastKnownStatus`.
* On mount:

  * If we detect an active run via other state (e.g. from API) and we have persisted `lastSequence`:

    * Attach SSE with `after_sequence = lastSequence`.
* Telemetry (NDJSON) for active runs is optional; we can begin directly from SSE in these cases.

---

## 10. Integration with Screens

### 10.1 Documents

* Live run card:

  * Uses `useRunStream(runId, { attachLive: true, skipIfCompleted: true })`.
  * Shows current phase and last console lines.
* Run history:

  * Doesn’t need streaming; uses static summaries from API.
* “Open full run”:

  * Navigates to Run Detail route with `runId` and optionally `sequence` for error deep link.

### 10.2 Run Detail

* On mount:

  * If we know run is completed (via API): use `useRunTelemetry(runId, { autoStart: true })`.
  * If run is active:

    * Option 1: first replay NDJSON, then attach live SSE.
    * Option 2 (simpler v1): attach SSE directly (no NDJSON), rely on streaming history for the current session.
* Replay slider:

  * Uses `setViewSequence` from `useRunStream`.
* “Jump to first error”:

  * Uses `firstErrorSequence` from state, calls `setViewSequence(firstErrorSequence)` and scrolls console.

### 10.3 Config Builder

* `useWorkbenchRun` handles starting runs and binding UI to streaming:

  * Calls run-creation API.
  * Once run is created, stores `runId` and uses `useRunStream(runId, { attachLive: true })`.
* Run panel controls:

  * For now, primarily in “live” mode; replay may be optional here.
* “View full run detail”:

  * Navigates to Run Detail route with `runId`.

---

## 11. Testing Requirements

Unit tests (Vitest):

* `runStreamReducer`:

  * Applies sequences correctly.
  * Ignores duplicates/out-of-order events.
  * Maintains derived slices (phases, console, validation).
* `useRunStream`:

  * Attaches/detaches live SSE (mocked).
  * `setViewSequence` replays subsets correctly.
* `useRunTelemetry`:

  * Handles NDJSON chunks correctly.
  * Stops at `upToSequence` when provided.
  * Handles malformed lines resiliently.

Integration/E2E (see `070-TEST-PLAN.md`):

* Live streaming behavior in Documents.
* Replay behavior and deep links in Run Detail.
* “Resume after reload” for active Config Builder run.

---

## 12. Implementation Notes & Conventions

* All streaming code lives under `features/runs/stream`.
* Only streaming hooks and provider are allowed to touch:

  * `EventSource`.
  * NDJSON `ReadableStream` parsing.
* Screens and other features must use `useRunStream` / `useRunTelemetry` and **never** reimplement streaming logic.
* If new AdeEvent types are added that affect UI:

  * Extend the AdeEvent union type.
  * Update reducer & relevant derived slices.
  * Update this spec with new behavior.

When in doubt about how to represent something (e.g. new event type, new phase status), update this spec first so future developers have a single place to look.
