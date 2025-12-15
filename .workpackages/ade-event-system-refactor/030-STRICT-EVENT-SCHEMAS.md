> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

### Core: unify event envelope + sinks

* [x] Define a single AD API event envelope matching engine `EventRecord` (dict-based; Pydantic optional only for strict API events).
* [x] Implement `RunEventStream` (append-to-file + SSE subscribers) as the single run event sink.
* [x] Implement `stream_engine_events()` to read NDJSON `EventRecord` lines from engine **stderr**.
* [x] Assign a per-run monotonic `sequence` in the API on every append (engine/build/API events) and persist it.

### Runs: remove AdeEvent plumbing

* [x] Update run orchestration to use engine stderr NDJSON instead of `engine-logs/events.ndjson`.
* [x] Remove RunEventDispatcher usage (emit/sequence/event_id wrapping).
* [x] Remove RunEventStorage and RunEventLogReader usage in run streaming + replay.
* [x] Update run SSE endpoint to stream `EventRecord` dicts (use `sequence` as SSE id; honor Last-Event-ID replay).

### Builds: keep build streaming consistent with the run stream (build config change)

* [x] Refactor `BuildsService.stream_build` to emit `EventRecord` dicts (not AdeEvent).
* [x] Ensure build events in run stream remain first-class and consistent (same envelope).
* [x] Replace build event dispatcher/storage/reader by reusing `RunEventStream` as a “build-only run” (no alternate/legacy stream).
* [x] Update build SSE endpoint `/builds/{build_id}/events/stream` to stream `EventRecord` dicts.

### Cleanup / deletion

* [x] Delete AdeEvent envelope types and payload schemas in AD API that become unused.
* [x] Remove engine telemetry file tailing logic (engine-logs directory creation, tailer tasks).
* [x] Remove legacy event_id-based pagination/cursoring; use `sequence` for SSE/replay.
* [x] Update docs/comments to reflect new unified pipeline. — docs/events-v1, ade-web docs, api/build notes refreshed

Agent note: docs updates completed to match the EventRecord pipeline.

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] {{CHECK_TASK_1_SUMMARY}} — {{SHORT_STATUS_OR_COMMIT_REF}}`

---

# Simplify AD API event pipeline (Runs + Builds) using engine NDJSON console stream

## 1. Objective

**Goal:**
Simplify the AD API event system by making the ADE engine’s NDJSON `EventRecord` output the canonical event stream, and having the AD API:

1. run the engine with NDJSON console logging,
2. capture NDJSON events from stderr,
3. enrich events with API context (jobId, workspaceId, buildId, configId),
4. assign a per-run monotonic `sequence` to every event in the API,
5. persist the unified stream to a single per-run `logs/events.ndjson`,
6. stream the same events over SSE (SSE `id` = `sequence`; Last-Event-ID replay),
7. keep build streaming consistent by emitting build events in the *same* envelope and including them in the run SSE stream.

You will:

* Remove AdeEvent and associated envelope complexity in the API.
* Remove dispatcher/storage/reader layers for runs.
* Adjust build streaming so build events appear in the run SSE stream in the same EventRecord structure.
* Preserve build-only streaming endpoints, but simplify them to reuse the same event format (and preferably the same streaming machinery).

The result should:

* One consistent event shape everywhere (engine/run/build/API events).
* A single per-run NDJSON file owned by the API.
* SSE stream produced by forwarding EventRecord dictionaries, with minimal transformation.
* Significant code deletion: no redundant event wrapping and no duplicate log stores.

---

## 2. Context (What you are starting from)

The ADE Engine emits structured telemetry as NDJSON. Historically, the AD API created its own event abstraction (`AdeEvent`) and a dispatcher/storage/reader pipeline to:

* re-wrap engine events,
* assign sequence numbers,
* store events in separate per-run logs,
* replay events and support SSE.

Builds also produce a streamed event structure, and those build events are included in the run SSE stream today. Build event streaming currently uses similar dispatcher/storage/reader abstractions and the AdeEvent envelope.

We want to remove this API-side event system and instead treat the engine’s NDJSON output as canonical. The API should behave as a thin adapter that enriches, persists, and streams events with minimal additional structure.

---

## 3. Target architecture / structure (ideal)

### 3.1 One canonical envelope: EventRecord (dict)

Engine and API events share the same top-level keys:

```jsonc
{
  "event_id": "<uuid4 hex>",
  "engine_run_id": "<uuid4 hex>" | "",
  "timestamp": "<RFC3339 UTC>",
  "level": "info" | "debug" | "warning" | "error" | "critical",
  "event": "<namespaced.event.name>",
  "message": "<human-readable message>",
  "data": { ... },
  "error": { ... optional ... }
}
```

> API adds a monotonically increasing `sequence` to each EventRecord when appending to the run stream; the engine never emits it.

### 3.2 One canonical sink per run: `logs/events.ndjson`

For each job/run, AD API owns:

```
<runs_root>/<workspace_id>/<job_id>/logs/events.ndjson
```

This file contains the unified event stream in order:

1. API-origin run events (`api.run.queued`, `api.run.completed`, etc.)
2. Build events (`build.*`, `console.line` with `data.scope="build"`), if build streaming is enabled
3. Engine events (`engine.*`, `console.line` with `data.scope="engine"` if desired)

### 3.3 Event stream plumbing

* `RunEventStream`:

  * append-to-file
  * in-memory subscribers for SSE
  * assign and stamp a per-run monotonic `sequence` field on every appended event
* `stream_engine_events()`:

  * read NDJSON lines from engine stderr
  * yield dict events
* Build streaming:

  * `BuildsService.stream_build` emits EventRecord dicts.
  * Those events are appended to the run’s `RunEventStream` (so they appear in the run SSE stream) and receive the next `sequence` values before engine events.
  * Build-only endpoints stream the same EventRecord format using the same RunEventStream abstraction (no parallel dispatcher/reader for compatibility).

> **Agent instruction:**
>
> * Keep this section in sync with reality.
> * If the design changes while coding, update this section and the file tree below.

```text
apps/ade-api/
  src/ade_api/features/runs/
    service.py                        # orchestration: build events + engine events → RunEventStream
    router.py                         # SSE endpoint streams EventRecord dicts
    runner.py                         # subprocess runner reads engine stderr NDJSON (stream_engine_events)
    event_stream.py                   # NEW: RunEventStream + helpers (append, subscribe)
  src/ade_api/features/builds/
    service.py                        # emits EventRecord dicts (no AdeEvent)
    router.py                         # streams EventRecord dicts (SSE/NDJSON)
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* **One event shape everywhere**: engine, builds, API events all use EventRecord.
* **Minimal moving parts**: no dispatcher/storage/reader stacks.
* **Build config change support**: build events remain included in run SSE stream and remain consistent.
* **Keep developer ergonomics**: build-only endpoints still exist but are thinner.
* **SSE-friendly**: SSE `id` uses the per-run `sequence`; `event_id` remains opaque for dedupe only.

### 4.2 Key components / modules

* `RunEventStream` — the only run event sink:

  * append NDJSON to file
  * fan out to SSE subscribers

* `stream_engine_events` — engine stderr NDJSON consumer:

  * parse JSON per line
  * yield EventRecord dicts

* `BuildsService.stream_build` — build event producer:

  * emits EventRecord dicts (build.* + console.line scope=build)

### 4.3 Key flows / pipelines

#### Run orchestration

1. Create `RunEventStream` for `<run_dir>/logs/events.ndjson`.
2. Append API-origin `api.run.queued` event.
3. If build streaming enabled:

   * call `BuildsService.stream_build()` and append each build event to the run stream (sequence assigned on append, precedes engine events).
4. Start engine subprocess:

   * read `stderr` NDJSON events via `stream_engine_events`.
   * enrich with `jobId`, `workspaceId`, etc.
   * append to run stream (sequence assigned on append).
5. Append API-origin `api.run.completed`.

#### Build-only streaming

* Build events are streamed in the same EventRecord format using `RunEventStream` (treat build-only streaming as a build-only run; do not add a fallback BuildEventStream). Sequence numbers still come from the same per-run counter.

### 4.4 Open questions / decisions

* Cursoring:

  * `sequence` is mandatory and monotonically increasing per run; SSE `id` uses `sequence`.
  * Replays use Last-Event-ID: skip `sequence <= last_event_id`, replay the rest from disk, then stream live.

* Build-only persistence:

  * Preferred: reuse run logs or reuse RunEventStream design.
  * Decide how build-only endpoints locate the file (build log file path vs run log path).

---

## 5. Implementation & notes for agents

### 5.1 Engine stderr NDJSON is canonical for engine events

* Run engine with ndjson formatting (stderr).
* Treat each stderr line as a single JSON record; ignore malformed lines.

### 5.2 Event enrichment happens only in the API

* Add `jobId`, `workspaceId`, and optionally `buildId`/`configurationId` into `data`.
* Do not re-wrap events into a new envelope.
* Assign `sequence` in the API when appending to the run stream (engine/build/API events).

### 5.3 API-origin events

Emit API events using the same EventRecord structure:

* `api.run.queued`
* `api.run.completed`
* optionally `api.build.reused`, etc.

### 5.4 Build streaming consistency

* Build events should use:

  * `event` names like `build.started`, `build.completed`, etc. (or `api.build.*` if you prefer)
  * `console.line` with `data.scope="build"` (preferred)

Build events must appear in the run SSE stream before engine events when builds are executed as part of run preparation.
* Build events get the next `sequence` values from the run stream counter so they can be replayed/resumed like engine/API events.

### 5.5 Replay / resume semantics

* SSE `Last-Event-ID` contains the last seen `sequence`.
* On connect, read `<run_dir>/logs/events.ndjson`, skip events where `sequence <= Last-Event-ID`, emit the rest in order, then attach to the live subscriber queue for new events.
* The same replay flow applies to build-only streaming (read the same log, same cursor rules).

---

# 6. Detailed overview of everything that needs to be removed / deleted / simplified

## 6.1 Remove AdeEvent envelope and associated models

Delete or stop using any AD API-only event wrapper types that include fields like:

* `sequence` (old AdeEvent envelope; new sequencing happens directly on EventRecords at append time)
* `created_at`
* `source`
* `payload`
* `run_id`/`build_id` in the envelope rather than in `data`

Any place that does `AdeEvent.model_validate_json(...)` should be replaced with `json.loads(...)` returning an EventRecord dict.

## 6.2 Remove run dispatcher/storage/reader system

Remove these responsibilities and code paths:

* assigning `sequence` inside dispatcher/storage layers (RunEventStream owns sequencing on append)
* creating “API NDJSON log” distinct from engine log
* subscription mechanisms tied to dispatcher emitters
* log re-readers tied to AdeEvent parsing

Replace with:

* `RunEventStream.append(event_dict)` (stamps `sequence`, enriches with run/build/API context)
* `RunEventStream.subscribe()`

## 6.3 Remove engine telemetry file tailing and engine-logs directory

Eliminate any run startup logic that:

* creates `engine-logs/`
* passes `--logs-dir` solely to support API telemetry
* tails `engine-logs/events.ndjson` to capture engine events

Replace with:

* capturing engine stderr NDJSON directly.

## 6.4 Simplify run SSE endpoint

Replace AdeEvent SSE formatting with EventRecord formatting:

```
id: <sequence>
event: ade.event
data: <EventRecord JSON>
```

Replay should read `logs/events.ndjson` directly, skip any events where `sequence <= Last-Event-ID`, then continue with new events from the live subscriber queue.

## 6.5 Build streaming simplification (build config change)

Build streaming currently reuses the same event envelope/dispatcher paradigm as runs. We are removing that as well.

### Remove build dispatcher/storage/reader

Delete or stop using:

* BuildEventDispatcher (sequence + persist + subscribe)
* BuildEventStorage
* build event log readers tied to AdeEvent

### Refactor BuildsService.stream_build

* Emit EventRecord dicts instead of AdeEvents.
* For build console output:

  * emit `console.line` with `data.scope="build"`.

### Ensure build events remain in the run SSE stream

* RunsService should append build EventRecords into the run stream before engine events.

### Build-only endpoints

* `/builds/{build_id}/events` should serve EventRecord lines (NDJSON / JSON list).
* `/builds/{build_id}/events/stream` should SSE-stream EventRecord dicts using the same SSE serializer (`id` = `sequence`).

* Treat build-only streaming as a “build-only run” and reuse `RunEventStream` (no fallback BuildEventStream or legacy path).
* Replay for build-only endpoints follows the same Last-Event-ID + file replay semantics as runs.

---

## 7. Acceptance criteria

* Run SSE stream contains (in order):

  1. `api.run.queued`
  2. build events (`build.*` and `console.line scope=build`) if build streaming enabled
  3. engine events (`engine.*`)
  4. `api.run.completed`

* Only one canonical run log exists: `<run_dir>/logs/events.ndjson`.

* All streamed/persisted events follow the EventRecord envelope and include an API-assigned `sequence`.

* AdeEvent is no longer used in runs or builds.

* Dispatcher/storage/reader stacks are removed or reduced to thin utilities; RunEventStream owns sequencing, append, subscribe.

* Build-only SSE and events endpoints still work and stream EventRecord dicts.
* SSE `id` equals `sequence`; Last-Event-ID resumes after the last seen sequence (replay from file then live).
