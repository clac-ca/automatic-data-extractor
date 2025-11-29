# 050 - ADE API Implementation (Runs, Events, Streaming)

Scope: How `ade-api` should implement the new run + event streaming system end-to-end.

> Important:
> This replaces the existing "v1" run/build streaming implementation.
> We do not need backward compatibility and will remove v1 endpoints + code as part of this work.

Related docs:

* `020-EVENT-TYPES-REFERENCE.md` - Canonical event envelope and payload schemas.
* `030-API-DESIGN-RUNS-AND-BUILDS.md` - Event types current vs new, keep/change/add.
* `060-EVENT-LOG-STORAGE.md` - NDJSON storage vs DB, retention, performance.
* `080-BUILD-STREAMING.md` - Build streaming behavior and UX.

This doc focuses specifically on ade-api behavior and code structure.

---

## 1. High-Level API Design

### 1.1 Goals

* One canonical run API:
  * `POST /runs` to start a run.
  * `GET /runs/{run_id}` to fetch run status + summary.
  * `GET /runs/{run_id}/events` for history and streaming.
* Unified event stream per run:
  * Contains both build and run events, in order, with `sequence`.
* Standard streaming:
  * SSE (`text/event-stream`) for live streaming.
  * NDJSON for bulk download / replay.
* Simple implementation:
  * ade-api owns:
    * Run/build IDs.
    * Event IDs + sequences.
    * Event persistence.
  * Engine just emits structured events + raw stdout/stderr; API wraps everything.

### 1.2 Out of scope (explicitly NOT doing)

* No `/v2` versioning.
* No row-per-event tables in the DB.
* No WebSockets, Kafka, or message brokers.
* No two parallel streams (build stream + run stream). Everything is in the run stream.

---

## 2. Routes and HTTP Contracts

We maintain the existing workspace/config scoping, but the implementation changes underneath.

Assume base path:

```
/workspaces/{workspace_id}/configurations/{configuration_id}
```

### 2.1 Start a run (non-streaming)

**Endpoint**

```http
POST /workspaces/{workspace_id}/configurations/{configuration_id}/runs
Content-Type: application/json
Accept: application/json
```

**Request body (example)**

```json
{
  "mode": "execute",              // "execute" | "validate_only" | "dry_run"
  "document_ids": ["doc_123"],
  "input_sheet_names": ["Sheet1"],
  "force_rebuild": false
}
```

**Behavior**

1. Validate workspace/config access.
2. Generate IDs (see 3):
   * `run_id`
   * `build_id` (even if we might reuse an existing build).
3. Create DB rows:
   * `runs` row with `status="queued"`.
   * Optionally a `builds` row if you track builds separately.
4. Emit:
   * `run.queued` (API-origin event).
   * `build.created` (API-origin event with reason/should_build).
5. Schedule the run execution worker (task queue/background job).
6. Return a small JSON resource:

   ```json
   {
     "run_id": "run_01JK3HXPQKZ4P6RZ3BET8ESZ1T",
     "build_id": "build_01JK3HXRRTKPM3M3G7AQ23SCV7",
     "status": "queued"
   }
   ```

### 2.2 Start + stream a run (SSE)

**Endpoint**

```http
POST /workspaces/{workspace_id}/configurations/{configuration_id}/runs?stream=true
Content-Type: application/json
Accept: text/event-stream
```

**Behavior**

Same as non-streaming, but:

1. After scheduling the worker, the handler switches to SSE mode:
   * Sends `HTTP 200`, `Content-Type: text/event-stream`.
   * Immediately starts streaming events for this `run_id`.
2. SSE stream semantics:
   * Each event:

     ```text
     id: <sequence>
     event: ade.event
     data: {<AdeEventEnvelope JSON>}

     ```

   * `id` = `sequence` (per-run monotonic).
   * `event` = `ade.event` (constant; clients look at JSON `type`).
3. The SSE stream must contain at least:
   * `run.queued`
   * `build.*` lifecycle
   * `console.line` (build + run)
   * `run.phase.*`
   * `run.table.summary`
   * `run.validation.summary` (if emitted by engine)
   * `run.completed` (with embedded summary)
4. The SSE connection ends after `run.completed` has been emitted and sent.

### 2.3 Get run info and summary

**Endpoint**

```http
GET /workspaces/{workspace_id}/configurations/{configuration_id}/runs/{run_id}
Accept: application/json
```

**Response (example)**

```json
{
  "run": {
    "id": "run_01JK3HXPQKZ4P6RZ3BET8ESZ1T",
    "workspace_id": "ws_123",
    "configuration_id": "cfg_456",
    "status": "succeeded",
    "created_at": "2025-11-28T18:52:57.397955Z",
    "updated_at": "2025-11-28T18:52:58.538808Z"
  },
  "summary": {
    /* RunSummary (see event model doc) */
  }
}
```

Backend reads this from the `runs` table (summary JSON column) and does not need to read events for this endpoint.

### 2.4 Get run events (JSON or NDJSON)

**Endpoint**

```http
GET /workspaces/{workspace_id}/configurations/{configuration_id}/runs/{run_id}/events
```

Two modes, depending on headers/query.

#### 2.4.1 JSON (paginated)

```http
GET /.../runs/{run_id}/events?after_sequence=0&limit=1000
Accept: application/json
```

**Response**

```json
{
  "events": [ /* AdeEventEnvelope[] */ ],
  "next_after_sequence": 100
}
```

Server:

* Reads NDJSON sequentially.
* Skips until `sequence > after_sequence`.
* Parses up to `limit` events.
* Returns them as JSON.

#### 2.4.2 NDJSON (raw)

```http
GET /.../runs/{run_id}/events
Accept: application/x-ndjson
```

Server:

* Streams the raw NDJSON file.
* Optionally supports `after_sequence` query to trim the start (by scanning until `sequence > after_sequence`).

### 2.5 Stream an existing run (SSE attach)

**Endpoint**

```http
GET /workspaces/{workspace_id}/configurations/{configuration_id}/runs/{run_id}/events?stream=true
Accept: text/event-stream
```

**Query params**:

* `after_sequence` (optional): replay only events with `sequence > after_sequence`.
* If absent, server starts at `sequence=1`.

**Behavior**

1. Replay phase:
   * Read NDJSON from events file.
   * Emit SSE events for envelopes where `sequence > after_sequence`.
2. Live phase:
   * Subscribe to in-memory dispatcher for this `run_id`.
   * Forward any newly emitted events as SSE.
3. Respect SSE `Last-Event-ID` header as a fallback for `after_sequence`.

---

## 3. ID Ownership and Metadata

### 3.1 `run_id` and `build_id`

Generated by ade-api only.

Suggested formats: `run_<ULID>` and `build_<ULID>`.

IDs must be globally unique and stable across restarts.

### 3.2 Event IDs and sequences

Generated by ade-api event dispatcher only.

* `event_id`: ULID/UUIDv7 string.
* `sequence`:
  * Int, starts at `1` per run.
  * Incremented by `1` for every event associated with that `run_id`.
  * Includes both API-origin and engine-origin events.

The engine never sets `event_id` or `sequence`.

### 3.3 Context fields

For every event envelope, the API ensures:

* `workspace_id`
* `configuration_id`
* `run_id`
* `build_id` (if applicable)
* `source`: `"api" | "engine" | "scheduler" | "worker"`

Engine can emit these fields into its own raw JSON; API can either:

* Trust and forward them, or
* Overwrite with API-known values. Safer to trust only `run_id` and `build_id` passed in env.

---

## 4. Event Dispatcher in ade-api

The event dispatcher is the central piece: it creates envelopes, writes them to storage, and fans them out to subscribers.

### 4.1 Responsibilities

For every event:

1. Assign `event_id` and `sequence`.
2. Stamp `created_at` and `source`.
3. Fill in `workspace_id`, `configuration_id`, `run_id`, `build_id`.
4. Write to NDJSON (see `060-EVENT-LOG-STORAGE.md`).
5. Broadcast to any live SSE subscribers for that `run_id`.
6. Return the envelope (for internal use/tests).

### 4.2 Suggested module layout

In `apps/ade-api/src/ade_api/events/dispatcher.py`:

```python
class RunEventDispatcher:
    def __init__(self, storage: EventStorage):
        self._storage = storage
        self._seq_by_run: dict[str, int] = {}
        self._subscribers: dict[str, list[asyncio.Queue[AdeEventEnvelope]]] = {}

    def _next_sequence(self, run_id: str) -> int:
        current = self._seq_by_run.get(run_id, 0) + 1
        self._seq_by_run[run_id] = current
        return current

    async def emit(
        self,
        *,
        type: str,
        source: Literal["api", "engine", "scheduler", "worker"],
        run_id: str,
        workspace_id: str,
        configuration_id: str,
        build_id: Optional[str],
        payload: dict,
    ) -> AdeEventEnvelope:
        sequence = self._next_sequence(run_id)
        event_id = generate_ulid()
        created_at = datetime.utcnow()

        envelope = AdeEventEnvelope(
            type=type,
            event_id=event_id,
            created_at=created_at,
            sequence=sequence,
            source=source,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            run_id=run_id,
            build_id=build_id,
            payload=payload,
        )

        await self._storage.append(run_id=run_id, event=envelope)
        await self._broadcast(run_id=run_id, event=envelope)
        return envelope

    async def _broadcast(self, run_id: str, event: AdeEventEnvelope) -> None:
        queues = self._subscribers.get(run_id, [])
        for q in queues:
            q.put_nowait(event)

    def subscribe(self, run_id: str) -> "AsyncIterator[AdeEventEnvelope]":
        queue: asyncio.Queue[AdeEventEnvelope] = asyncio.Queue()
        self._subscribers.setdefault(run_id, []).append(queue)

        async def iterator():
            try:
                while True:
                    yield await queue.get()
            finally:
                self._subscribers[run_id].remove(queue)

        return iterator()
```

This is conceptual; exact code will depend on your async patterns.

### 4.3 Storage abstraction

`EventStorage` hides NDJSON file handling:

```python
class EventStorage(Protocol):
    async def append(self, *, run_id: str, event: AdeEventEnvelope) -> None:
        ...

    async def read(
        self,
        *,
        run_id: str,
        after_sequence: int = 0,
    ) -> AsyncIterator[AdeEventEnvelope]:
        ...
```

Actual implementation:

* Uses the path layout specified in `060-EVENT-LOG-STORAGE.md`.
* Performs append-only writes.
* Reads sequentially for replay.

---

## 5. Run and Build Orchestration in ade-api

### 5.1 Run creation path

In `apps/ade-api/src/ade_api/features/runs/router.py`:

1. `POST /runs` handler:
   * Resolves workspace/config.
   * Validates body (`RunCreateRequest`).
   * Calls `RunService.create_run(...)`.
2. `RunService.create_run`:
   * Generates `run_id`, `build_id`.
   * Writes rows to DB.
   * Emits:
     * `run.queued` with mode and options.
     * `build.created` with reason and should_build.
   * Enqueues background work (`RunWorker.run(run_id, build_id, ...)`).
   * Returns a resource DTO.
3. If `stream=true`:
   * After scheduling, handler calls `RunStreamService.stream(run_id)` which:
     * Replays events (likely just the first 1-2 that exist).
     * Subscribes to dispatcher for new events.
     * Writes SSE until `run.completed`.

### 5.2 Build behavior

`RunWorker` handles:

1. Deciding whether to rebuild or reuse:
   * Build fingerprint.
   * `force_rebuild` option.
2. Emitting build lifecycle events via dispatcher:
   * `build.started`
   * `build.phase.started` / `build.phase.completed`
   * `build.completed`

Key change from v1: these events are now run-scoped and flow through the same dispatcher as run events. They show up in the run stream and NDJSON log.

### 5.3 Run execution behavior

`RunWorker` (or equivalent) then:

1. Emits `run.started` (API-origin), including engine version hint, config version, and whether env was reused.
2. Launches the engine subprocess (see 6).
3. Waits for engine to complete.
4. After engine completion:
   * Calls `RunSummaryBuilder.build(run_id)` to compute summary from events.
   * Emits `run.completed` (API-origin, canonical).
   * Updates `runs` DB row with status, exit code, timings, summary JSON.
5. On error at any step:
   * Emits `run.error` with stage/code/message.
   * Emits `run.completed` with `status="failed"`.

Rule: Exactly one `run.completed` per `run_id`, always API-origin.

---

## 6. Subprocess and Consoles: Streaming Engine Output

### 6.1 Engine subprocess model

`RunWorker` starts the engine using the build's virtualenv:

```python
proc = await asyncio.create_subprocess_exec(
    python_bin,
    "-m",
    "ade_engine.main",
    env=engine_env,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
```

We then concurrently read `stdout` and `stderr` line-by-line.

### 6.2 Mixed structured events and raw console

To keep things simple and flexible:

* The engine writes both:
  * Structured JSON events (one JSON object per line) via its `emit_event(...)` helper.
  * Raw text that user code prints (`print`, loggers, etc.).

Worker line handler:

```python
async def handle_stdout_line(line: bytes):
    text = line.decode("utf-8", errors="replace").rstrip("\n")
    event = try_parse_engine_event(text)
    if event is not None:
        await dispatcher.emit(
            type=event["type"],
            source="engine",
            run_id=run_id,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
            payload=event.get("payload", {}),
        )
    else:
        await dispatcher.emit(
            type="console.line",
            source="engine",
            run_id=run_id,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
            payload={
                "scope": current_scope,  # "build" or "run" depending on stage
                "stream": "stdout",
                "level": "info",
                "message": text,
            },
        )
```

Analogous for `stderr` with defaults `stream: "stderr"`, `level: "error"`.

### 6.3 Determining `scope: "build" | "run"`

Track a simple current stage state in `RunWorker`:

* Start: `scope = "build"` until `build.completed`.
* After `build.completed` (status `"succeeded"` or `"reused"`): switch to `scope = "run"`.

Implementation:

* Small enum `RunStage` = `BUILDING` | `RUNNING` | `DONE`.
* Update stage when API emits `build.started`, `build.completed`, and `run.started`.
* When wrapping raw stdout/stderr to `console.line`, use `stage.value` as `scope`.

### 6.4 Avoiding conflicts

Engine structured `console.line` events are preferred if present; API should only wrap non-JSON lines. If a line parses as JSON with a `type` field, treat it as canonical and do not wrap it again.

---

## 7. Summary Building and Run Finalization

### 7.1 RunSummaryBuilder

In `apps/ade-api/src/ade_api/features/runs/summary_builder.py`:

* Reads events from `EventStorage.read(run_id)`.
* Looks for:
  * `run.queued`
  * `run.started`
  * `build.completed`
  * `run.phase.*`
  * `run.table.summary`
  * `run.validation.summary`
  * Engine completion info (exit_code, timings) from engine or worker context.
* Aggregates into a `RunSummary` (see event model doc).

### 7.2 Emitting `run.completed`

Only ade-api may emit `run.completed`:

* After engine process finishes and summary is built (or at least status and exit code known).

Pseudo:

```python
summary = RunSummaryBuilder(storage).build(run_id)
status, failure, execution = derive_final_status(summary, worker_result)

await dispatcher.emit(
    type="run.completed",
    source="api",
    run_id=run_id,
    workspace_id=workspace_id,
    configuration_id=configuration_id,
    build_id=build_id,
    payload={
        "status": status,
        "failure": failure,
        "execution": execution,
        "artifacts": {
            "output_paths": worker_result.output_paths,
            "events_path": runs_row.events_path,
        },
        "summary": summary.dict(),
    },
)
```

Also update `runs` DB row with status, exit code, started_at, completed_at, summary_json.

### 7.3 Error paths

If build fails:

* Emit `build.completed` with `status="failed"`.
* Emit `run.error` with `stage="build"`.
* Emit `run.completed` with `status="failed"` and `failure.stage="build"`.

If engine fails:

* Engine can emit `run.error` structured event.
* Worker sees non-zero `exit_code`.
* API emits `run.completed` with `status="failed"` and includes engine error info.

---

## 8. Current v1 references to clean up (ade-api/engine/web)

These still mention `run.console` / `build.console` or v1 streaming semantics and should be updated or removed during implementation:

- ade-api: `apps/ade-api/src/ade_api/features/runs/router.py` and `.../service.py` emit `run.console`/`build.console`; tests at `apps/ade-api/tests/unit/features/runs/test_runs_service.py` assert old shapes.
- ade-api: build streaming NDJSON path in `apps/ade-api/src/ade_api/features/builds/router.py` and `.../service.py` emits `build.console`.
- ade-engine: telemetry docs/code/tests in `apps/ade-engine/docs/07-telemetry-events.md`, `docs/11-ade-event-model.md`, `src/ade_engine/infra/telemetry.py`, `tests/test_telemetry.py` describe/emit `run.console`/`build.console`.
- ade-web: docs `apps/ade-web/docs/04-data-layer-and-backend-contracts.md`, `docs/07-documents-and-runs.md`; shared types `apps/ade-web/src/shared/runs/types.ts`; console utils `apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/console.ts` and tests expect `run.console`/`build.console`.

Use this list as a checklist when swapping everything to the unified `console.line` and new endpoints.

---

## 9. Removing v1 and Migration Plan

Because we have no external users, we can replace v1 in place:

1. Introduce new types and dispatcher:
   * Add new envelope + payload models (no URI versioning).
   * Implement `RunEventDispatcher` + `EventStorage`.
2. Wire new dispatcher into run/build orchestration:
   * Replace v1 event emission with `dispatcher.emit(...)`.
   * Ensure new event types match the spec in `020-EVENT-TYPES-REFERENCE.md`.
3. Replace v1 run/build endpoints:
   * Keep paths the same, but swap implementation to use new run creation + worker logic and new SSE event streaming.
   * Deprecate/remove old build streaming endpoint implementation that emitted `build.console` / `run.console` v1 events.
4. Update tests:
   * Add integration tests: happy path, build failure, engine failure.
   * Remove tests that assert v1 event payloads.
5. Code cleanup:
   * Remove old AdeEvent envelope variant(s) and run/build streaming helpers.
   * Update docs to reference new event types and endpoints/streaming semantics.

---

## 10. Implementation Checklist (ade-api)

* [ ] Implement `AdeEventEnvelope` + payload models in ade-api.
* [ ] Implement `EventStorage` for NDJSON append/read (per run).
* [ ] Implement `RunEventDispatcher` with sequence + subscriber management.
* [ ] Update run/build services to emit new event types via dispatcher.
* [ ] Implement `RunWorker` engine execution wrapper with stdout/stderr parsing and `console.line` emission.
* [ ] Implement `RunSummaryBuilder` and final `run.completed` emission.
* [ ] Implement HTTP endpoints:
  * `POST /.../runs` (JSON).
  * `POST /.../runs?stream=true` (SSE).
  * `GET /.../runs/{run_id}` (JSON).
  * `GET /.../runs/{run_id}/events` (JSON + NDJSON).
  * `GET /.../runs/{run_id}/events?stream=true` (SSE attach).
* [ ] Remove v1 event types and streaming code (build + run).
* [ ] Add integration tests for happy path, build failure, engine failure, and replay.

---

This doc should give backend devs everything they need to implement the new API cleanly, while other docs nail down the event shapes, storage, and frontend wiring.
