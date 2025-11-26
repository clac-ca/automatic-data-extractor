# Telemetry Events (engine-side logging & streaming)

This document describes the **engine-side telemetry event system**: how
`ade_engine` emits events into `events.ndjson`, how those events are modeled in
code, and how they fit into the unified ADE event model.

It focuses on:

- What the engine writes to `events.ndjson`.
- How pipeline code and configs log through `PipelineLogger`.
- How this relates to `artifact.json` and to the unified `ade.event/v1`
  envelope described in `11-ade-event-model.md`.

If you want the system-wide story (builds, API run streaming, DB
persistence), read `11-ade-event-model.md` after this.

---

## 1. Where telemetry fits

Each engine run produces two complementary outputs:

- **Artifact** – `artifact.json` (see `06-artifact-json.md`)

  - Run-level snapshot.
  - Mapping summary, validation summary, tables, and durable notes.
  - Designed for post-run inspection and reporting.

- **Telemetry** – `events.ndjson` (this doc)

  - Line-based event stream.
  - Lifecycle, pipeline phases, per-table summaries, notes, and optional
    fine-grained events.
  - Designed for streaming (e.g. ADE API tailing the file) and for
    log aggregation.

Conceptually:

> `artifact.json` answers **“What is the final outcome?”**  
> `events.ndjson` answers **“What happened, in order, while we got there?”**

All telemetry events use the unified ADE event envelope, `ade.event/v1`,
described in `11-ade-event-model.md`. The engine is responsible for emitting
run-scoped `ade.event` instances to `events.ndjson`.

---

## 2. Unified ADE event envelope (engine view)

The unified ADE event model defines a single envelope:

```jsonc
{
  "type": "run.pipeline.progress",   // primary discriminator
  "object": "ade.event",
  "schema": "ade.event/v1",
  "version": "1.0.0",

  "created_at": "2025-11-26T12:00:00Z",

  // Correlation (nullable where not applicable)
  "workspace_id": "ws_123",
  "configuration_id": "cfg_123",
  "run_id": "run_123",
  "build_id": null,

  // Namespaced payloads (only some are present per event)
  "run": { },
  "build": null,
  "env": null,
  "validation": null,
  "execution": null,
  "output_delta": null,
  "log": null,
  "error": null
}
```

Engine telemetry uses a subset of the global type space:

* `run.started` / `run.completed` (engine-level lifecycle)
* `run.pipeline.progress`
* `run.table.summary`
* `run.validation.issue.delta` (optional, fine-grained)
* `run.note`
* `run.log.delta` (optional; stdout/stderr bridged via API or direct)

The ADE API later:

* Tails `events.ndjson`.
* Forwards these envelopes to clients as-is.
* Adds its own events (`run.created`, `run.env.plan`, API-level
  `run.completed`, etc.) using the same envelope.

See `11-ade-event-model.md` for the full type catalog. This document stays
engine-centric.

---

## 3. Engine data model (Python types)

Within the engine, the unified envelope is represented by Pydantic models
(similar to earlier `TelemetryEvent` / `TelemetryEnvelope`, just aligned to
`ade.event/v1`).

At a high level:

```python
# ade_engine/schemas/telemetry.py (conceptual)

class AdeEvent(BaseModel):
    type: str                     # e.g. "run.started", "run.table.summary"
    object: Literal["ade.event"]
    schema: Literal["ade.event/v1"]
    version: str

    created_at: datetime

    workspace_id: str | None = None
    configuration_id: str | None = None
    run_id: str | None = None
    build_id: str | None = None

    run: RunPayload | None = None
    build: BuildPayload | None = None
    env: EnvPayload | None = None
    validation: ValidationPayload | None = None
    execution: ExecutionPayload | None = None
    output_delta: OutputDeltaPayload | None = None
    log: LogPayload | None = None
    error: ErrorPayload | None = None
```

Notes:

* Engine code only emits run-scoped events, so `build_id` and `build`
  are always `null` here.
* `workspace_id` / `configuration_id` are copied from
  `RunContext.metadata` when present, but are treated as opaque tags by
  the engine.
* The `RunPayload`, `ValidationPayload`, etc. are small Pydantic models with
  event-specific fields (e.g. `phase` for pipeline progress, `row_count` for
  table summaries).

These models can generate JSON Schema for external consumers if needed, but
the JSON on disk is the `AdeEvent` envelope itself.

---

## 4. Event sinks

### 4.1 EventSink protocol

Internally, sinks implement a minimal protocol:

```python
class EventSink(Protocol):
    def emit(self, event: AdeEvent) -> None:
        ...
```

Higher-level helpers (`PipelineLogger`) build `AdeEvent` instances and pass
them to the sink.

### 4.2 FileEventSink

The default sink is file-backed:

* One NDJSON file per run:
  `RunPaths.events_path` (typically `<logs_dir>/events.ndjson`).
* Each call to `emit(...)`:

  * JSON-serializes the `AdeEvent`,
  * writes a line ending in `\n`.

Guarantees:

* File exists for every run (even if empty on early failures).
* Lines are well-formed JSON objects.
* Events appear in the order they were emitted.

### 4.3 DispatchEventSink (fan-out)

A composite sink can fan out events to multiple sinks:

* `FileEventSink` + console logging.
* `FileEventSink` + streaming to a message bus.

Each run gets its own sink instance. This is configured via `TelemetryConfig`
(see below).

---

## 5. TelemetryConfig and per-run bindings

### 5.1 TelemetryConfig

`TelemetryConfig` is passed to the `Engine` at construction and controls how
telemetry is wired:

Conceptually:

```python
@dataclass
class TelemetryConfig:
    min_level: str = "info"       # "debug" | "info" | "warning" | "error"
    make_event_sink: Callable[[RunContext], EventSink] | None = None
```

* `min_level` lets you filter out very noisy events.
* `make_event_sink` builds the sink for a particular run; if `None`, a default
  `FileEventSink` is created pointing at `RunPaths.events_path`.

### 5.2 Per-run bindings

For each run, the engine constructs a small binding object that holds:

* `events: EventSink`
* `artifact: ArtifactSink`
* `logger: PipelineLogger` (wrapping both)

These bindings:

* Are per run, not global.
* Decorate every event with:

  * `schema`, `version`, `created_at`,
  * `run_id`, and
  * any correlation metadata from `RunContext.metadata` that you decide to
    surface (`workspace_id`, `configuration_id`, etc.).

---

## 6. PipelineLogger

`PipelineLogger` is the only thing pipeline code and config scripts should
touch. It hides envelope construction and sink details.

Conceptual API:

```python
class PipelineLogger:
    def note(self, message: str, *, level: str = "info", **details: Any) -> None: ...
    def event(self, type_suffix: str, *, level: str = "info", **payload: Any) -> None: ...
    def pipeline_phase(self, phase: str, **payload: Any) -> None: ...
    def table_summary(self, **table_payload: Any) -> None: ...
```

### 6.1 `note(...)` – narrative notes

* Adds a human-readable note to the artifact’s `notes` section.
* Also emits an ADE event with `type: "run.note"`:

  ```jsonc
  {
    "type": "run.note",
    "object": "ade.event",
    "run": {
      "message": "Run started",
      "level": "info",
      "details": {
        "files": 1
      }
    }
  }
  ```

Use this for durable breadcrumbs you want in both the artifact and telemetry.

### 6.2 `event(...)` – arbitrary ADE events

* Builds an ADE event named `f"run.{type_suffix}"`.
* Only writes to telemetry (does not touch the artifact unless you do so
  yourself).

Example:

```python
logger.event(
    "validation.issue.delta",
    level="warning",
    field="email",
    row_index=10,
    code="invalid_format",
)
```

Produces:

```jsonc
{
  "type": "run.validation.issue.delta",
  "object": "ade.event",
  "validation": {
    "field": "email",
    "row_index": 10,
    "code": "invalid_format",
    "severity": "warning"
  }
}
```

### 6.3 `pipeline_phase(...)` – standardized phase transitions

Short-hand for emitting `run.pipeline.progress` ADE events:

```python
logger.pipeline_phase(
    "extracting",
    file_count=3,
)
```

→

```jsonc
{
  "type": "run.pipeline.progress",
  "object": "ade.event",
  "run": {
    "phase": "extracting",
    "file_count": 3
  }
}
```

Phases align with `RunPhase` values:

* `initialization`
* `load_config`
* `extracting`
* `mapping`
* `normalizing`
* `writing_output`
* `hooks`
* `completed`
* `failed`

### 6.4 `table_summary(...)` – per-table aggregate

Used by the engine when a table has been fully processed:

```python
logger.table_summary(
    source_file="input.xlsx",
    source_sheet="Sheet1",
    table_index=0,
    row_count=123,
    validation_issue_counts={"error": 2, "warning": 5},
)
```

→

```jsonc
{
  "type": "run.table.summary",
  "object": "ade.event",
  "output_delta": {
    "kind": "table_summary",
    "table": {
      "source_file": "input.xlsx",
      "source_sheet": "Sheet1",
      "table_index": 0,
      "row_count": 123,
      "validation_issue_counts": {
        "error": 2,
        "warning": 5
      }
    }
  }
}
```

---

## 7. Standard engine-emitted events

The engine emits a small, consistent set of ADE event types.

### 7.1 Lifecycle

Emitted by the engine itself (API also emits additional lifecycle events):

* `run.started`

  * Emitted once after initialization and config load succeed.
  * `run` payload typically includes `engine_version` and basic input summary.

* `run.completed`

  * Emitted once at the end of pipeline execution (success or failure).
  * Engine-view only: `run.engine_status: "succeeded" | "failed"`, plus any
    engine-level error details.
  * API will later emit its own `run.completed` summarizing the whole run
    (env + engine + persistence).

* `run.pipeline.progress`

  * Emitted on each phase transition; `run.phase` = one of `RunPhase.value`.

### 7.2 Tables

* `run.table.summary`

  * Emitted once per `NormalizedTable`, after mapping/normalization.
  * Includes per-table row count and validation issue counts.

### 7.3 Validation

* `run.validation.issue.delta` (optional)

  * Emitted when you want streaming visibility into validation issues.

  * Payload mirrors `ValidationIssue`:

    * `row_index`
    * `field`
    * `code`
    * `severity`
    * optional `message` / `details`

  * Not required for correctness; artifact remains the authoritative list of
    issues.

### 7.4 Notes

* `run.note`

  * Emitted whenever `logger.note(...)` is used.
  * Mirrors artifact `notes` entries.

### 7.5 Logs

Depending on configuration, you may also see:

* `run.log.delta`

  * Used when the API bridges stdout/stderr into ADE events.

  * Payload:

    ```jsonc
    {
      "log": {
        "stream": "stdout" | "stderr",
        "message": "raw line..."
      }
    }
    ```

  * Engine itself does not have to emit this; it can be injected at the
    process boundary.

---

## 8. NDJSON file format

Telemetry is written to:

```text
<logs_dir>/events.ndjson
```

Properties:

* One event per line, no commas, plain `\n` separator.
* Each line parses to a complete `ade.event/v1` object.
* Empty lines are not used.

Example (abridged):

```text
{"type":"run.started","object":"ade.event","schema":"ade.event/v1","version":"1.0.0","run_id":"run_1","created_at":"2025-11-26T12:00:00Z","run":{"engine_version":"0.2.0"}}
{"type":"run.pipeline.progress","object":"ade.event","schema":"ade.event/v1","version":"1.0.0","run_id":"run_1","created_at":"2025-11-26T12:00:01Z","run":{"phase":"extracting","file_count":1}}
{"type":"run.table.summary","object":"ade.event","schema":"ade.event/v1","version":"1.0.0","run_id":"run_1","created_at":"2025-11-26T12:00:05Z","output_delta":{"kind":"table_summary","table":{"source_file":"input.xlsx","source_sheet":"Sheet1","table_index":0,"row_count":123,"validation_issue_counts":{"error":2}}}}
{"type":"run.completed","object":"ade.event","schema":"ade.event/v1","version":"1.0.0","run_id":"run_1","created_at":"2025-11-26T12:00:07Z","run":{"engine_status":"succeeded"}}
```

Consumers (ADE API, log processors) can treat `events.ndjson` as a standard
NDJSON stream.

---

## 9. Consumption by ADE API

From the engine’s perspective, the ADE API is just a consumer of
`events.ndjson`. Typical usage:

* Streaming UI

  * Tail `events.ndjson` while the run process is alive.
  * Forward ADE events to clients (websocket, SSE, etc.).
  * Combine engine events with API-emitted events like `run.created`,
    `run.env.plan`, and API-level `run.completed`.

* Post-run analysis

  * Read `events.ndjson` after completion.
  * Compute metrics (duration, #tables, #issues).
  * Feed logs into a log index or monitoring system.

The engine never depends on how events are consumed; it only guarantees the
envelope shape and ordering.

---

## 10. Best practices

### 10.1 For engine maintainers

* Keep the set of engine-emitted event types small and stable.
* Prefer additive changes:

  * New fields in existing payloads.
  * New event types with clear names.
* For breaking changes, bump `schema`/`version` (see `11-ade-event-model.md`).

### 10.2 For config authors

* Use `logger.note(...)` for durable notes that should appear in
  `artifact.json` and telemetry.
* Use `logger.event(...)` for domain-specific streaming signals (e.g.,
  `validation.issue.delta`, `quality_score.computed`).
* Keep payloads small, JSON-serializable, and stable.

### 10.3 For backend integrators

* Treat `events.ndjson` as a log source, not a primary data store.
* Use `artifact.json` for detailed reporting and queries.
* If you attach extra sinks (HTTP, queues, etc.), ensure failures in those
  sinks do not crash the run; they should degrade gracefully.

With this model, engine telemetry is predictable, streamable, and aligned to
the ADE-wide event envelope, while `artifact.json` remains the canonical audit
record.
