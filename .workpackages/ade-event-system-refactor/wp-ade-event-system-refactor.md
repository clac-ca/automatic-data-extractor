> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [ ] {{CHECK_TASK_1_SUMMARY}}
* [ ] {{CHECK_TASK_2_SUMMARY}}
* [ ] {{CHECK_TASK_3_SUMMARY}}
* [ ] {{CHECK_TASK_4_SUMMARY}}
* [ ] {{CHECK_TASK_5_SUMMARY}}

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] {{CHECK_TASK_1_SUMMARY}} — {{SHORT_STATUS_OR_COMMIT_REF}}`

Here’s an updated top-of-doc block you can paste into your work package, followed by a refined implementation plan that’s aligned with the design we just settled on.

---

> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.
>
> ---

## Work Package Checklist

* [ ] Define canonical `ade.event/v2` envelope & event payload models in ade‑api and ade‑engine shared code.
* [ ] Implement central event dispatcher in ade‑api (ID/sequence assignment, NDJSON sink, SSE fan‑out).
* [ ] Add v2 HTTP endpoints for runs and streaming (`POST /v2/runs`, `POST /v2/runs?stream=true`, `GET /v2/runs/{run_id}/events`).
* [ ] Refactor run/build orchestration in ade‑api to emit the new lifecycle events (`run.queued`, `build.*`, `run.phase.*`, `console.line`, etc.) via the dispatcher.
* [ ] Implement `RunSummaryBuilder` in ade‑api and wire it into run finalization to emit canonical `run.completed` and update the runs table.
* [ ] Update ade‑engine to emit structured internal events (build phases, run phases, `console.line`, `run.table.summary`, optional validation summary) using the new payload shapes.
* [ ] Wire ade‑engine’s NDJSON event output into ade‑api’s dispatcher (parse engine events, wrap in envelope, assign `event_id`/`sequence`).
* [ ] Update ade‑web config builder console to consume the v2 streaming endpoints and render `console.line`, phase banners, and table summaries.
* [ ] Add tests, metrics, and operational safeguards (backpressure, error handling, migration/removal of legacy event formats and IDs).

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] Implement central event dispatcher — merged in #1234`

---

## Refined Implementation Plan

Below is a concrete plan your devs can follow. It’s sequenced to minimize risk and keep changes incremental, even though we *don’t* care about backwards‑compat at the schema level.

I’ll break it into phases that map to the checklist.

---

### Phase 1 – Core types & envelope (foundation)

**Goal:** Introduce the canonical event model (`ade.event/v2`) and run summary types as shared, library‑style code. No behavioral change yet.

**Tasks (maps to checklist #1):**

1. **Define envelope types in ade‑api**
   In a shared module, e.g. `apps/ade-api/src/ade_api/events/models.py`:

   * `AdeEventEnvelope` with fields:

     ```python
     class AdeEventEnvelope(BaseModel):
         type: str
         event_id: str
         created_at: datetime
         sequence: int
         source: Literal["api", "engine", "scheduler", "worker"]

         workspace_id: str
         configuration_id: str
         run_id: str
         build_id: Optional[str] = None

         payload: dict  # or a union of typed payloads
     ```

   * Enumerations or constants for:

     * event types (`RUN_QUEUED`, `BUILD_COMPLETED`, etc.)
     * phases (`BUILD_PHASE_…`, `RUN_PHASE_…`).

2. **Define payload models**
   In the same module or `events/payloads.py`, define Pydantic models for:

   * `RunQueuedPayload`
   * `RunStartedPayload`
   * `RunCompletedPayload` (with embedded `RunSummary`)
   * `BuildCreatedPayload`, `BuildStartedPayload`, `BuildCompletedPayload`
   * `BuildPhaseStartedPayload`, `BuildPhaseCompletedPayload`
   * `RunPhaseStartedPayload`, `RunPhaseCompletedPayload`
   * `ConsoleLinePayload`
   * `RunTableSummaryPayload`
   * (Optional) `RunValidationSummaryPayload`
   * `RunErrorPayload`

   Even if you expose `payload: dict` in the envelope, strongly typed payload models will keep you honest in the code.

3. **Define `RunSummary` type**
   In `apps/ade-api/src/ade_api/features/runs/summary.py` (or similar):

   ```python
   class RunSummary(BaseModel):
       run: RunSummaryRunInfo
       core: RunSummaryCore
       breakdowns: RunSummaryBreakdowns
   ```

   Match the structure we defined (`run`, `core`, `breakdowns.by_file`, `breakdowns.by_field`).

**Exit criteria for Phase 1:**

* Types compile and are importable by both the run/build services and any future event dispatcher.
* No runtime behavior has changed yet.

---

### Phase 2 – Event dispatcher & NDJSON sink

**Goal:** Centralize event emission & persistence in ade‑api, but *still* not yet hooked into engine/run flows.

**Tasks (checklist #2):**

1. **Implement global sequence allocator per run**

   * Add a simple storage for sequence numbers, tied to `run_id`. Options:

     * In‑memory `dict` keyed by `run_id` (for a single process).
     * Or a DB column in the `runs` table (e.g. `last_event_sequence` with `UPDATE ... RETURNING` semantics).
   * For now, you can start with in‑memory if the API is single‑process; decide later if you need persistency.

2. **Implement `emit_event` dispatcher**
   In e.g. `apps/ade-api/src/ade_api/events/dispatcher.py`:

   ```python
   def emit_event(
       *,
       type: str,
       source: Literal["api", "engine", "scheduler", "worker"],
       run_id: str,
       workspace_id: str,
       configuration_id: str,
       build_id: Optional[str],
       payload: BaseModel | dict,
   ) -> AdeEventEnvelope:
       # 1. Allocate sequence = next_sequence(run_id)
       # 2. event_id = generate_ulid()
       # 3. created_at = datetime.utcnow()
       # 4. Build envelope
       # 5. Append to NDJSON log sink
       # 6. Broadcast to any live SSE subscribers (Phase 3)
       # 7. Return envelope
   ```

3. **NDJSON sink implementation**

   * Implement a `RunEventLogWriter` that:

     * Derives path: `.../workspaces/{workspace_id}/runs/{run_id}/logs/events.ndjson`.
     * Appends `json.dumps(envelope)` + `"\n"` on each event.
   * Make sure:

     * It’s safe to call repeatedly (open/append/close or long‑lived file object).
     * Failures are logged and surfaced — if event logging fails, you may still want to keep the run going, but at least alert.

4. **Event reader for replay**

   * Add `RunEventLogReader` that:

     * Iterates over NDJSON lines.
     * Parses each into `AdeEventEnvelope`.
     * Supports filtering by `sequence` range.

**Exit criteria for Phase 2:**

* You can call `emit_event(...)` from a test harness and see:

  * NDJSON log file created and appended.
  * Envelopes have monotonically increasing `sequence` for a given `run_id`.

---

### Phase 3 – v2 HTTP endpoints & SSE streaming

**Goal:** Add the new `/v2` HTTP surface & streaming wiring, backed by the dispatcher and NDJSON sinks.

**Tasks (checklist #3):**

1. **Add v2 routes module**
   In `apps/ade-api/src/ade_api/features/runs/router_v2.py` (for clarity), implement:

   * `POST /v2/runs`
   * `POST /v2/runs?stream=true`
   * `GET /v2/runs/{run_id}`
   * `GET /v2/runs/{run_id}/events` (JSON/NDJSON)
   * `GET /v2/runs/{run_id}/events?stream=true`

2. **Implement `POST /v2/runs` (non-streaming)**

   * Generate `run_id` and `build_id` in `RunServiceV2`.
   * Insert DB row for run + build.
   * Call `emit_event(type="run.queued", source="api", ...)` with full `mode` and `options`.
   * Enqueue job for execution (same or similar to existing background helper).
   * Return JSON:

     ```json
     {
       "run_id": "...",
       "build_id": "...",
       "status": "queued"
     }
     ```

3. **Implement `POST /v2/runs?stream=true` (SSE)**

   * Same as above, but:

     * After queueing the run, upgrade response to `text/event-stream`.
     * Immediately replay the events emitted so far (at least `run.queued`, `build.created` if already created).
     * Then subscribe to a per‑run event queue so that any new `emit_event` for that run gets pushed on the SSE stream.

4. **Implement `GET /v2/runs/{run_id}/events`**

   * JSON mode: read events via `RunEventLogReader` and return paginated `events` array + `next_after_sequence`.
   * NDJSON mode (`Accept: application/x-ndjson`): stream the log file as‑is.

5. **Implement `GET /v2/runs/{run_id}/events?stream=true`**

   * Accept optional `from_sequence` or use SSE `Last-Event-ID`.
   * Behavior:

     * Replay any events from log where `sequence >= from_sequence`.
     * After replay, subscribe to in‑memory queue for new events.

6. **Set up a simple in‑memory subscriber registry**

   * Map `run_id` → list of async queues.
   * `emit_event` broadcasts each new event to any subscribers for its `run_id`.

**Exit criteria for Phase 3:**

* You can:

  * Create a run with `stream=true` and see SSE events as JSON envelopes with proper `sequence`.
  * Attach to `/v2/runs/{run_id}/events?stream=true` and see the same events replayed from the top.

---

### Phase 4 – Refactor ade‑api run/build orchestration to use the new events

**Goal:** All run/build activity in ade‑api should emit well‑structured events via `emit_event`, and nothing should be hand‑crafting raw event JSON.

**Tasks (checklist #4):**

1. **Refactor run creation**
   In `apps/ade-api/src/ade_api/features/runs/service.py`:

   * Replace existing custom event calls with:

     * `run.queued` right after `run_id`/`build_id` creation.
     * `build.created` when deciding build reuse vs new build.

2. **Build lifecycle events**
   In `build` services (wherever you orchestrate the env creation):

   * At build start: `build.started`.
   * For each phase:

     * Before: `build.phase.started` with `phase` & `message`.
     * After: `build.phase.completed` with `status`, `duration_ms`.
   * At end: `build.completed` with `status`, `exit_code`, `env.reason`, `env.reused`.

3. **Transition logs**

   * After `build.completed` succeeds:

     * Emit a `console.line` with `scope:"run"` and message `"Configuration build completed; starting ADE run."`.
   * If build fails:

     * Emit `run.error` describing cause.
     * Emit `run.completed` with failure metadata.

4. **Run lifecycle events (API‑side)**

   * When engine execution is about to start (or exactly when it starts):

     * Emit `run.started` with `engine_version`, `config_version`, `env.reason`, `env.reused`.
   * For failure/cancel conditions:

     * Ensure `run.completed` is emitted with appropriate `status` and `failure`.

**Exit criteria for Phase 4:**

* A run that is fully handled by ade‑api (without engine) would still produce a logically complete stream: `run.queued` → `build.*` → `run.started` → `run.completed`.

---

### Phase 5 – RunSummaryBuilder & canonical `run.completed`

**Goal:** Build the run summary deterministically from events and emit the single canonical `run.completed`.

**Tasks (checklist #5):**

1. **Implement `RunSummaryBuilder`**
   In e.g. `apps/ade-api/src/ade_api/features/runs/summary_builder.py`:

   * Constructor takes a `RunEventLogReader`.
   * `build(run_id: str) -> RunSummary`:

     * Iterate over events.
     * Track:

       * start/end times (from `run.started` & either engine completion or `run.completed` fallback).
       * build env info from `build.completed`.
       * run status & failure (from `run.error` and final process result).
       * counters from `run.table.summary` and `run.validation.summary`.
   * Return a `RunSummary` instance.

2. **Integrate into run finalization**

   * Wherever you currently finalize a run after engine completion:

     ```python
     summary = RunSummaryBuilder(reader).build(run_id)
     emit_event(
         type="run.completed",
         source="api",
         run_id=run_id,
         workspace_id=summary.run.workspace_id,
         configuration_id=summary.run.configuration_id,
         build_id=build_id,
         payload=RunCompletedPayload(
             status=summary.run.status,
             failure=...,
             execution=...,
             artifacts=...,
             summary=summary,
         ),
     )
     ```

   * Also update the `runs` DB table with:

     * `status`, `exit_code`, `started_at`, `completed_at`, `summary_json`.

3. **Ensure only one `run.completed` per run**

   * Guard in code: if a run is already marked completed, don’t emit a second event.
   * That keeps the stream clean and easier to reason about.

**Exit criteria for Phase 5:**

* For a successful run, events show exactly:

  * `run.queued` → `build.*` → `run.started` → `run.phase.*` → `run.table.summary` → `run.completed`.
* `GET /v2/runs/{run_id}` returns the same `summary` that was emitted in `run.completed`.

---

### Phase 6 – ade‑engine event emission

**Goal:** Engine emits structured internal events that map 1:1 into the v2 payloads.

**Tasks (checklist #6):**

1. **Introduce engine event helper**
   In `apps/ade-engine/src/ade_engine/infra/telemetry.py`:

   ```python
   def emit_engine_event(type: str, payload: dict) -> None:
       event = {
           "type": type,
           "created_at": now_iso8601(),
           "source": "engine",
           "workspace_id": os.environ["ADE_WORKSPACE_ID"],
           "configuration_id": os.environ["ADE_CONFIGURATION_ID"],
           "run_id": os.environ["ADE_RUN_ID"],
           "build_id": os.environ.get("ADE_BUILD_ID"),
           "payload": payload,
       }
       sys.stdout.write(json.dumps(event) + "\n")
       sys.stdout.flush()
   ```

   This is *not yet* the full v2 envelope (no `event_id`, `sequence`); ade‑api will wrap it.

2. **Emit build events from engine/build script**

   * On build start/end and each phase, emit:

     * `build.started`
     * `build.phase.started` / `build.phase.completed`
     * `build.completed` (or hand that to API if build is API‑driven).
   * Wrap pip logs / output into `console.line` with `scope:"build"`.

3. **Emit run events from engine**

   * At start: `run.phase.started` for `"extracting"`.
   * After phases: `run.phase.completed` with metrics.
   * For logs: `console.line` with `scope:"run"`.
   * After mapping: `run.table.summary` once per normalized table.
   * Optionally `run.validation.summary`.

4. **Standardize table IDs**

   * Implement deterministic `table_id` generation per run as described (e.g., `tbl_<hash>_<sheet_index>_<table_index>`).
   * Ensure you never emit duplicate `table_id`s without a version field.

**Exit criteria for Phase 6:**

* If you run engine standalone and pipe stdout, you see well‑shaped JSON events that match the `payload` schemas.

---

### Phase 7 – ade‑engine → ade‑api wiring

**Goal:** Parse engine’s NDJSON output and route it through `emit_event` to become canonical envelopes with `event_id` and `sequence`.

**Tasks (checklist #7):**

1. **Adapt the worker that runs the engine**

   * Instead of capturing engine output as plain text logs:

     * Treat each line as a JSON event from engine.
     * Parse it into a `dict`, validate minimal fields (`type`, `payload`, `run_id`, etc.).
   * For each parsed event:

     ```python
     emit_event(
         type=engine_event["type"],
         source="engine",
         run_id=engine_event["run_id"],
         workspace_id=engine_event["workspace_id"],
         configuration_id=engine_event["configuration_id"],
         build_id=engine_event.get("build_id"),
         payload=engine_event["payload"],
     )
     ```

2. **Ensure no engine‑side event_id/sequence**

   * If engine includes those for its own reasons, either ignore them or rename them (e.g. `engine_sequence`) before wrapping.

3. **Exit code & completion**

   * After engine process exits:

     * Emit a small internal signal to the “finalizer” so it can:

       * Kick off `RunSummaryBuilder`.
       * Emit canonical `run.completed`.

**Exit criteria for Phase 7:**

* Running a real run through the full stack produces:

  * NDJSON logs of canonical envelopes (with `event_id` and `sequence`).
  * SSE streams that match those logs exactly.

---

### Phase 8 – ade‑web UI integration

**Goal:** The config builder console uses the new SSE endpoints and v2 event shapes, and renders a clear build + run story.

**Tasks (checklist #8):**

1. **Update config builder workbench**
   In `apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/Workbench.tsx`:

   * Switch from the old streaming endpoint to:

     * `POST /v2/runs?stream=true` for run start.
     * Or `GET /v2/runs/{run_id}/events?stream=true` if you want to reattach.
   * For each incoming SSE event:

     * Parse the `data` as JSON → `AdeEventEnvelope`.
     * Route based on `type`:

       * `console.line` → append line to console, with visual grouping by `scope` and `phase`.
       * `build.phase.*` / `run.phase.*` → show banners or progress markers.
       * `run.table.summary` → update any “results” pane with mapping/validation overview.
       * `run.completed` → stop spinners, show completion status and summary.

2. **UI for phases**

   * Distinct banners/messages for:

     * “Building environment…” (`build.phase.started` first event).
     * “Running ADE…” (after build completed).
   * Optionally show durations per phase using `*.phase.completed.payload.duration_ms`.

3. **Handle reconnect/resume**

   * If the user refreshes the page:

     * Call `GET /v2/runs/{run_id}/events?stream=true&from_sequence=1` to rebuild console.
     * Or rely on SSE `Last-Event-ID` to resume.

**Exit criteria for Phase 8:**

* From the user’s point of view:

  * Pressing “Run” shows a single, continuous stream with build logs first, then run logs.
  * They can navigate away and back and still see the same logs via replay.

---

### Phase 9 – Tests, metrics, and cleanup

**Goal:** Make this robust and remove legacy paths.

**Tasks (checklist #9):**

1. **Unit tests**

   * `RunSummaryBuilder`: feed synthetic event sequences and assert summary values.
   * Event dispatcher: ensure sequence is monotonic and persisted correctly.
   * NDJSON read/write: check round‑trip correctness.

2. **Integration tests**

   * “Happy path” full run:

     * Start run (non‑streaming), wait for completion.
     * Assert:

       * `events.ndjson` contains logically correct sequence of events.
       * `run.completed` is present and summary matches `run.table.summary` aggregates.
   * “Build fails”:

     * Simulate pip error.
     * Assert:

       * `build.completed.status="failed"`.
       * `run.completed.status="failed"` with appropriate `failure.stage="build"`.

3. **Metrics & logging**

   * Emit metrics for:

     * events per run
     * bytes written per log file
     * failures in event writing & SSE errors
   * Log warnings when event parsing from engine fails.

4. **Cleanup legacy code**

   * Remove:

     * Old event shapes and builders.
     * Multiple run IDs per stream (the “engine UUID” as `run_id`).
     * Any “all fields always” serialization logic.
   * Make v2 the only supported event system in backend and UI.

---

If you’d like, I can next turn this into:

* A “DEV_README: ADE Events v2” file you can drop into the repo, plus
* Concrete Pydantic/TS interface stubs for the main envelope and payloads.


----

1. **Goals & constraints**
2. **Architecture & ID ownership** (who makes `run_id`/`build_id`, where)
3. **Streaming vs storage format (SSE vs NDJSON)**
4. **Canonical event envelope** (exact JSON shape)
5. **Event types & payloads** (catalog)
6. **Run summary model** (what goes into `run.completed`)
7. **HTTP API surface** (endpoints & semantics)
8. **Implementation notes for ade‑api**
9. **Implementation notes for ade‑engine**

No backward compatibility; this is v2 and you can break v1.  We can remove v1 code as we work where needed.  At the end of the work package, we want all references to v1 removed and replaced with v2 (documentation, code etc..)

---

## 1. Goals & constraints

We’re designing this for:

* **Single, intuitive user experience**

  * “Run” from the config builder → one continuous console that shows:

    * queue → build → run → summary
* **One canonical source of truth**

  * There is one **run ID** that everything hangs off of.
  * Build and run logs share one event stream.
* **Simple to consume**

  * UI / CLI: subscribe to a stream of JSON events.
  * Backend: ingest same shapes for persistence & summary.
* **Easy to implement**

  * ade‑api orchestrates and owns IDs.
  * ade‑engine emits structured events; API turns them into final envelopes.

---

## 2. Architecture & ID ownership

### 2.1 Entities

We care about:

* **Run**

  * “Execute config X against inputs Y.”
  * Identified by `run_id`.
* **Build**

  * “Prepare env to execute config X (venv, pip install, config package, import checks).”
  * Identified by `build_id`.
  * A run may:

    * Trigger a build.
    * Reuse an existing build.
    * Skip build entirely (e.g., prebuilt env).

### 2.2 Who creates which IDs?

**Decision:**

* **ade‑api** (the HTTP backend) is the **only component** that generates:

  * `run_id`: string, e.g. `run_01JK3HXPQKZ4P6RZ3BET8ESZ1T`
  * `build_id`: string, e.g. `build_01JK3HXRRTKPM3M3G7AQ23SCV7`

* **ade‑engine** never creates or changes `run_id` or `build_id`.
  It receives them as part of the job payload (CLI args or env).

If the engine wants its own internal ID for logging, call it `engine_run_id` and keep it inside the event payload; it’s never exposed as `run_id`.

### 2.3 Job payload from API → engine

When ade‑api enqueues work for the engine, it passes a job with at least:

```json
{
  "run_id": "run_...",
  "build_id": "build_...",
  "workspace_id": "01KB4X3NBV07JBJS92MA5A1TSC",
  "configuration_id": "01KB4X3XK9GTZCVJ2E8DQRY910",

  "mode": "execute",         // "execute" | "validate_only" | "dry_run"
  "options": {
    "document_ids": ["01KB4X3VCE0FJ2HK2J416S05F7"],
    "input_sheet_names": ["Sheet1"],
    "force_rebuild": true
  }
}
```

You can deliver this as:

* JSON over a worker queue, and/or
* Env vars:

  * `ADE_RUN_ID`
  * `ADE_BUILD_ID`
  * `ADE_WORKSPACE_ID`
  * `ADE_CONFIGURATION_ID`
  * `ADE_RUN_OPTIONS_JSON` (full JSON string)

Engine uses these values *as‑is* in emitted events.

---

## 3. Streaming vs storage format

### 3.1 Streaming: **SSE** (Server‑Sent Events)

For live streaming to UI / CLI, we use SSE:

* Endpoint: `text/event-stream`
* Format per message:

  ```text
  id: <sequence>
  event: ade.event
  data: {<JSON envelope>}

  ```

**Why SSE over raw NDJSON?**

* Works natively in browsers (`EventSource`).
* Well understood for “LLM-ish” streaming APIs.
* Supports reconnection via `Last-Event-ID`.

We’ll use:

* `id: <sequence>` so the browser’s `Last-Event-ID` gives us the last sequence.
* `event: ade.event` (constant): clients ignore it and look at the JSON `type`.

### 3.2 Storage: **NDJSON**

The same JSON envelope is stored as **one JSON object per line** in an NDJSON file:

* `.../runs/{run_id}/logs/events.ndjson`

Example:

```text
{"type":"run.queued","event_id":"evt_...","sequence":1,...}
{"type":"build.created","event_id":"evt_...","sequence":2,...}
...
{"type":"run.completed","event_id":"evt_...","sequence":N,...}
```

This NDJSON is the source of truth for:

* Post‑mortem debugging.
* Rebuilding summaries.
* Offline tools.

---

## 4. Canonical event envelope

Every event you emit or consume has this shape:

```jsonc
{
  "type": "run.phase.started",        // event type string
  "event_id": "evt_01JK3J0YRKJ...",   // globally unique
  "created_at": "2025-11-28T18:52:57.802612Z",  // ISO-8601 UTC timestamp
  "sequence": 23,                     // monotonic per run_id

  "source": "engine",                 // "api" | "engine" | "scheduler" | "worker"

  "workspace_id": "01KB4X3NBV07JBJS92MA5A1TSC",
  "configuration_id": "01KB4X3XK9GTZCVJ2E8DQRY910",
  "run_id": "run_01JK3HXPQKZ4P6RZ3BET8ESZ1T",
  "build_id": "build_01JK3HXRRTKPM3M3G7AQ23SCV7",

  "payload": { /* type-specific stuff */ }
}
```

**Rules:**

* Required fields:

  * `type`, `event_id`, `created_at`, `sequence`, `source`,
  * `workspace_id`, `configuration_id`, `run_id`, `payload`.
* `build_id`:

  * Present for all build events.
  * For run events, set if there is an associated build; otherwise omit or set null.
* `event_id`: created only by ade‑api (e.g. ULID/UUIDv7).
* `sequence`: created only by ade‑api’s per‑run dispatcher:

  * Starts at `1`.
  * Increments by `1` for each event for that `run_id`.
  * Includes both API‑generated and engine‑generated events.

Engine events may be produced without `event_id`/`sequence` in a “pre‑envelope”; ade‑api then wraps them into this canonical envelope when streaming/persisting.

**No “all fields always” rule:**

* The only always-present fields are the envelope ones listed above.
* Everything event‑specific lives under `payload`, and you only put fields there that make sense for that event type.

---

## 5. Event type catalog

Here’s the set of event types you implement, with payloads.

I’ll keep them focused and regular — devs should never have to guess.

### 5.1 Run lifecycle

#### 5.1.1 `run.queued`

First event emitted for a run; created by ade‑api after the run row is created and the job is enqueued.

```json
{
  "type": "run.queued",
  "payload": {
    "status": "queued",
    "mode": "execute",     // "execute" | "validate_only" | "dry_run"
    "options": {
      "document_ids": ["01KB4X3VCE0FJ2HK2J416S05F7"],
      "input_sheet_names": ["Sheet1"],
      "force_rebuild": true,
      "dry_run": false,
      "validate_only": false
    },
    "queued_by": {
      "user_id": "usr_123",   // optional
      "email": "user@example.com"
    }
  }
}
```

#### 5.1.2 `run.started`

Emitted when the engine is about to begin the core run pipeline (build ready or skipped).

Produced by ade‑api just before invoking the engine OR by the engine at the very start — choose *one* and stick with it. I’d lean API so we guarantee it fires even if engine crashes immediately.

```json
{
  "type": "run.started",
  "payload": {
    "status": "in_progress",
    "engine_version": "0.2.0",
    "config_version": "0.2.0",
    "env": {
      "reason": "force_rebuild",     // "force_rebuild" | "cache_hit" | "cache_miss" | "reuse"
      "reused": false
    }
  }
}
```

#### 5.1.3 `run.completed` (canonical)

Exactly **one** per run, emitted by ade‑api when everything is done (success/failure/cancel).

```json
{
  "type": "run.completed",
  "payload": {
    "status": "succeeded",            // "succeeded" | "failed" | "cancelled"
    "failure": {
      "code": null,                   // e.g. "build_failed", "engine_error"
      "stage": null,                  // "build" | "run" | "validation" | null
      "message": null
    },
    "execution": {
      "exit_code": 0,
      "started_at": "2025-11-28T18:52:57.397955Z",
      "completed_at": "2025-11-28T18:52:58.538808Z",
      "duration_ms": 1141
    },
    "artifacts": {
      "output_paths": [
        "s3://ade/....../runs/run_01JK3HXP.../output/normalized.xlsx"
      ],
      "events_path": "s3://ade/....../runs/run_01JK3HXP.../logs/events.ndjson"
    },
    "summary": { /* RunSummary, see section 6 */ }
  }
}
```

> The engine can still emit its own internal “run finished” event, but that is not exposed as a public event type; instead, API uses it to know when to compute the summary and emit this single canonical `run.completed`.

---

### 5.2 Build lifecycle

#### 5.2.1 `build.created`

Emitted by ade‑api right after it decides which build to use for a run.

```json
{
  "type": "build.created",
  "payload": {
    "status": "queued",
    "engine_spec": "apps/ade-engine",
    "engine_version_hint": "0.2.0",
    "reason": "force_rebuild",         // "force_rebuild" | "cache_hit" | "manual"
    "should_build": true               // false if we know we’ll reuse
  }
}
```

#### 5.2.2 `build.started`

Emitted when the build actually begins (engine side).

```json
{
  "type": "build.started",
  "payload": {
    "status": "building",
    "reason": "force_rebuild"
  }
}
```

#### 5.2.3 `build.phase.started`

Per-phase start within the build:

```json
{
  "type": "build.phase.started",
  "payload": {
    "phase": "install_engine",         // "create_venv" | "upgrade_pip" | "install_engine" | "install_config" | "verify_imports" | "collect_metadata"
    "message": "Installing engine: apps/ade-engine"
  }
}
```

#### 5.2.4 `build.phase.completed`

Corresponding completion with duration:

```json
{
  "type": "build.phase.completed",
  "payload": {
    "phase": "install_engine",
    "status": "succeeded",            // "succeeded" | "failed" | "skipped"
    "duration_ms": 2450,
    "message": "Engine installed"
  }
}
```

#### 5.2.5 `build.completed`

Emitted when build is fully done (or failed):

```json
{
  "type": "build.completed",
  "payload": {
    "status": "succeeded",            // "succeeded" | "failed" | "reused" | "skipped"
    "exit_code": 0,
    "summary": "Build succeeded",
    "duration_ms": 12238,
    "env": {
      "reason": "force_rebuild",      // keep in sync with create_reason
      "reused": false
    },
    "error": null                      // or { code, message, details } if failed
  }
}
```

If build fails, ade‑api:

* Emits this `build.completed` with `status:"failed"`.
* Emits a `run.error` (see below).
* Emits `run.completed` with `status:"failed"` and `failure.stage:"build"`.

---

### 5.3 Run phases

#### 5.3.1 `run.phase.started`

Engine marks logical phases of the run:

```json
{
  "type": "run.phase.started",
  "payload": {
    "phase": "extracting",    // "extracting" | "mapping" | "normalizing" | "validating" | "writing_output"
    "message": "Extracting tables from input"
  }
}
```

#### 5.3.2 `run.phase.completed`

```json
{
  "type": "run.phase.completed",
  "payload": {
    "phase": "extracting",
    "status": "succeeded",    // "succeeded" | "failed" | "skipped"
    "duration_ms": 350,
    "message": "Finished extract phase",
    "metrics": {
      "table_count": 2,
      "row_count": 2646
    }
  }
}
```

---

### 5.4 Console / logs

We unify logs into a single type, with a `scope` field.

#### 5.4.1 `console.line`

```json
{
  "type": "console.line",
  "payload": {
    "scope": "build",                   // "build" | "run"
    "phase": "install_engine",          // optional
    "stream": "stdout",                 // "stdout" | "stderr"
    "level": "info",                    // "debug" | "info" | "warn" | "error"
    "message": "Successfully installed ade-engine-0.2.0",
    "engine_timestamp": 1764384774      // optional numeric timestamp
  }
}
```

Examples:

* UX banner from API when transitioning from build → run:

  ```json
  {
    "type": "console.line",
    "payload": {
      "scope": "run",
      "stream": "stdout",
      "level": "info",
      "message": "Configuration build completed; starting ADE run."
    }
  }
  ```

UI logic for the config builder console is trivial: render all `console.line` events in order; optionally visually group by `scope` and `phase`.

---

### 5.5 Table & validation summary

#### 5.5.1 `run.table.summary`

One per logical table per run, from engine.

**ID rule:**

* Must be unique per run.
* Suggested:

  ```text
  table_id = "tbl_" + short_hash(source_file) + "_" + sheet_index + "_" + table_index
  ```

Payload:

```json
{
  "type": "run.table.summary",
  "payload": {
    "table_id": "tbl_6F12A_0_0",
    "source_file": "s3://.../Ledcor.xlsx",
    "source_sheet": "Sheet1",
    "file_index": 0,
    "sheet_index": 0,
    "table_index": 0,

    "row_count": 1323,
    "column_count": 50,

    "mapping": {
      "mapped_columns": [
        {
          "field": "member_id",
          "header": "",
          "source_column_index": -1,
          "score": 0.0,
          "is_required": true,
          "is_satisfied": false
        },
        {
          "field": "first_name",
          "header": "First Name",
          "source_column_index": 6,
          "score": 0.9,
          "is_required": false,
          "is_satisfied": true
        }
      ],
      "unmapped_columns": [
        {
          "header": "Co.",
          "source_column_index": 0,
          "output_header": "raw_1"
        }
        // ...
      ]
    },

    "validation": {
      "total": 0,
      "issues_total": 0,
      "issues_by_severity": {},
      "issues_by_code": {},
      "issues_by_field": {},
      "max_severity": null
    },

    "metadata": {
      "header_row": 4,
      "first_data_row": 5,
      "last_data_row": 1327
    }
  }
}
```

Guarantees:

* At most one `run.table.summary` per `table_id` (unless you explicitly add a versioning field such as `iteration` and document that).
* That’s enough for the summary builder and UI.

#### 5.5.2 `run.validation.summary` (optional)

If engine wants to emit run‑level validation stats:

```json
{
  "type": "run.validation.summary",
  "payload": {
    "issue_counts_total": 0,
    "issue_counts_by_severity": {},
    "issue_counts_by_code": {},
    "issue_counts_by_field": {}
  }
}
```

---

### 5.6 Error events

#### 5.6.1 `run.error`

Additional context when something goes wrong.

```json
{
  "type": "run.error",
  "payload": {
    "stage": "build",                  // "build" | "run" | "validation" | ...
    "phase": "install_engine",         // optional
    "code": "PIP_INSTALL_FAILED",
    "message": "pip exited with code 1 while installing apps/ade-engine",
    "details": {
      "exit_code": 1,
      "last_lines": [
        "ERROR: Could not build wheels..."
      ]
    }
  }
}
```

**Rule:**
Any failure must ultimately be reflected in `run.completed.payload.status = "failed"`. `run.error` is additional context, not a replacement.

---

## 6. Run summary model

This is embedded as `payload.summary` in `run.completed` and also stored in your `runs` table.

```jsonc
{
  "run": {
    "id": "run_01JK3HXPQKZ4P6RZ3BET8ESZ1T",
    "workspace_id": "01KB4X3NBV07JBJS92MA5A1TSC",
    "configuration_id": "01KB4X3XK9GTZCVJ2E8DQRY910",
    "configuration_version": "0",
    "status": "succeeded",              // final status
    "failure_code": null,
    "failure_stage": null,
    "failure_message": null,
    "engine_version": "0.2.0",
    "config_version": "0.2.0",
    "env_reason": "force_rebuild",
    "env_reused": false,
    "started_at": "2025-11-28T18:52:57.397955Z",
    "completed_at": "2025-11-28T18:52:58.538808Z",
    "duration_seconds": 1.140853
  },
  "core": {
    "input_file_count": 1,
    "input_sheet_count": 1,
    "table_count": 2,
    "row_count": 2646,
    "canonical_field_count": 4,
    "required_field_count": 2,
    "mapped_field_count": 4,
    "unmapped_column_count": 92,
    "validation_issue_count_total": 0,
    "issue_counts_by_severity": {},
    "issue_counts_by_code": {}
  },
  "breakdowns": {
    "by_file": [
      {
        "source_file": "s3://.../Ledcor.xlsx",
        "table_count": 2,
        "row_count": 2646,
        "validation_issue_count_total": 0,
        "issue_counts_by_severity": {},
        "issue_counts_by_code": {}
      }
    ],
    "by_field": [
      {
        "field": "member_id",
        "label": "Member ID",
        "required": true,
        "mapped": true,
        "max_score": 0.0,
        "validation_issue_count_total": 0,
        "issue_counts_by_severity": {},
        "issue_counts_by_code": {}
      }
      // ...
    ]
  }
}
```

### 6.1 How it’s built

Implement a `RunSummaryBuilder` in ade‑api:

* Input: all canonical events for `run_id`, in `sequence` order.

* It listens for:

  * `run.queued` → initial mode/options.
  * `run.started` → engine/config versions, env reason/reused.
  * `build.completed` → env_reason/env_reused/duration.
  * `run.table.summary` → file/field breakdowns & core metrics.
  * `run.validation.summary` → optional validation aggregate.
  * engine completion → exit code, start/end times.

* Output: a `RunSummary` object as above.

You call this builder right before emitting `run.completed`, and embed the result.

---

## 7. HTTP API surface

### 7.1 Create & stream a run (for IDE)

**Request**

```http
POST /v2/runs?stream=true
Content-Type: application/json
Accept: text/event-stream

{
  "workspace_id": "01KB4X3NBV07JBJS92MA5A1TSC",
  "configuration_id": "01KB4X3XK9GTZCVJ2E8DQRY910",
  "mode": "execute",
  "document_ids": ["01KB4X3VCE0FJ2HK2J416S05F7"],
  "input_sheet_names": ["Sheet1"],
  "force_rebuild": true
}
```

**Response**

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
```

Body (SSE):

```text
id: 1
event: ade.event
data: {"type":"run.queued", ...}

id: 2
event: ade.event
data: {"type":"build.created", ...}

id: 3
event: ade.event
data: {"type":"build.started", ...}

...

id: 20
event: ade.event
data: {"type":"build.completed", ...}

id: 21
event: ade.event
data: {"type":"console.line","payload":{"scope":"run","message":"Configuration build completed; starting ADE run.", ...}}

...

id: 35
event: ade.event
data: {"type":"run.table.summary", ...}

...

id: 42
event: ade.event
data: {"type":"run.completed", ...}
```

The browser’s `EventSource` will automatically send `Last-Event-ID` if it reconnects; your server can resume from `sequence > Last-Event-ID`.

### 7.2 Create run without streaming

```http
POST /v2/runs
Accept: application/json
```

Response:

```json
{
  "run_id": "run_01JK3HXPQKZ4P6RZ3BET8ESZ1T",
  "build_id": "build_01JK3HXRRTKPM3M3G7AQ23SCV7",
  "status": "queued"
}
```

Clients can then:

* Poll `/v2/runs/{run_id}`, or
* Connect to `/v2/runs/{run_id}/events?stream=true`.

### 7.3 Stream an existing run

```http
GET /v2/runs/{run_id}/events?stream=true&from_sequence=21
Accept: text/event-stream
```

Server behavior:

* If `from_sequence` provided:

  * Load events from storage where `sequence >= from_sequence` and replay them.
  * Then continue streaming new events.
* If not provided:

  * Start at `sequence=1`.

Alternative: rely solely on SSE’s `Last-Event-ID` header, which your server will read and treat as `from_sequence`.

### 7.4 Get run metadata & summary

```http
GET /v2/runs/{run_id}
Accept: application/json
```

Response:

```json
{
  "run": {
    "id": "run_...",
    "workspace_id": "...",
    "configuration_id": "...",
    "status": "succeeded",
    "created_at": "...",
    "updated_at": "..."
  },
  "summary": { /* RunSummary */ }
}
```

### 7.5 Get full event log

JSON array:

```http
GET /v2/runs/{run_id}/events?after_sequence=0&limit=1000
Accept: application/json
```

```json
{
  "events": [ AdeEventEnvelope, ... ],
  "next_after_sequence": 100   // or null if none
}
```

NDJSON:

```http
GET /v2/runs/{run_id}/events
Accept: application/x-ndjson
```

Returns raw NDJSON file; each line is one envelope.

---

## 8. Implementation notes – ade‑api

### 8.1 Event dispatcher

Create a central function:

```python
def emit_event(run_id: str, type: str, payload: dict, *, source: str, build_id: Optional[str] = None) -> AdeEventEnvelope:
    # 1. Look up run context (workspace_id, configuration_id).
    # 2. Get next sequence for run_id (atomic counter).
    # 3. Construct envelope:
    #    - event_id, created_at, sequence, source, IDs, payload
    # 4. Append to NDJSON sink.
    # 5. Push to any live SSE subscribers for this run.
    # 6. Return envelope (for internal use/testing).
```

All API and engine events flow through this.

### 8.2 SSE streaming

For `POST /v2/runs?stream=true` and `GET /v2/runs/{run_id}/events?stream=true`:

* Maintain an in‑memory async queue per `run_id`.

* Whenever `emit_event` is called for that run, push the envelope onto the queue.

* SSE handler pulls from the queue and writes:

  ```text
  id: {sequence}
  event: ade.event
  data: {json}

  ```

* Also multiplex replay:

  * For `from_sequence`, read stored NDJSON up to the current end, then subscribe for new events.

### 8.3 Persistence

* On each `emit_event`, append to:

  ```text
  data/workspaces/{workspace_id}/runs/{run_id}/logs/events.ndjson
  ```

* That file is append‑only and ordered by `sequence`.

### 8.4 Summary building & finalization

* When the engine finishes (e.g. worker result with exit_code, output paths):

  * Call `RunSummaryBuilder.build(run_id)` → `RunSummary`.
  * Emit `run.completed` with:

    * `status`, `failure`, `execution`, `artifacts`, `summary`.
  * Update `runs` DB row with:

    * `status`, `exit_code`, `started_at`, `completed_at`, `summary_json`.

* If the engine or build crashes:

  * Emit `run.error`.
  * Emit `run.completed` with `status:"failed"` & failure metadata.

---

## 9. Implementation notes – ade‑engine

### 9.1 Inputs

Engine process receives:

* `ADE_RUN_ID`
* `ADE_BUILD_ID`
* `ADE_WORKSPACE_ID`
* `ADE_CONFIGURATION_ID`
* `ADE_RUN_OPTIONS_JSON`

It must treat these as authoritative.

### 9.2 Event emitter

Provide a simple helper inside engine:

```python
def emit_event(type: str, payload: dict) -> None:
    event = {
        "type": type,
        "created_at": now_iso8601(),
        "source": "engine",
        "workspace_id": ADE_WORKSPACE_ID,
        "configuration_id": ADE_CONFIGURATION_ID,
        "run_id": ADE_RUN_ID,
        "build_id": ADE_BUILD_ID,
        "payload": payload,
    }
    # Write as one-line JSON to stdout, or send over IPC channel.
```

ade‑api reads these, assigns `event_id` + `sequence`, and turns them into canonical envelopes.

### 9.3 What the engine must emit

* Build:

  * `build.started`
  * `build.phase.started` / `build.phase.completed` for each logical step.
  * `console.line` for pip / build output (`scope:"build"`).
  * `build.completed` (with `status`, `exit_code`, `duration_ms`, `env.reason`, `env.reused`).
* Run:

  * `run.phase.started` / `run.phase.completed` for extract/mapping/normalize/validate/write.
  * `console.line` for run prints (`scope:"run"`).
  * `run.table.summary` once per table.
  * `run.validation.summary` if you want extra aggregate.
  * An internal “run finished” indicator event or result that ade‑api uses, but not exposed as an external event type.

### 9.4 Error handling

* On failures, engine should:

  * Emit a `run.error` with stage/phase/code/message/details.
  * Emit a `build.completed` or “engine finished” indicator with non‑zero exit_code.
* ade‑api will then:

  * Mark the run as failed via `run.completed`.

---

If you want, next step I can turn this into:

* Concrete Pydantic models (for Python) for `AdeEventEnvelope`, `RunSummary`, and each payload type.
* A small skeleton of:

  * `POST /v2/runs?stream=true` SSE handler.
  * `emit_event` dispatcher.
  * `RunSummaryBuilder` stub.

But this spec alone should be enough for devs to implement the end‑to‑end v2 event system without guessing.
