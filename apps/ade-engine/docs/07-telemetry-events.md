# Telemetry Events

This document describes the **telemetry event system** used by the ADE engine:
how events are modeled, written, filtered, and consumed via `events.ndjson`.

It focuses on the **event stream**, not on `artifact.json`. For the artifact
schema, see `06-artifact-json.md`.

## Terminology

| Concept        | Term in code      | Notes                                                     |
| -------------- | ----------------- | --------------------------------------------------------- |
| Run            | `run`             | One call to `Engine.run()` or one CLI invocation          |
| Config package | `config_package`  | Installed `ade_config` package for this run               |
| Config version | `manifest.version`| Version declared by the config package manifest           |
| Build          | build             | Virtual environment built for a specific config version   |
| User data file | `source_file`     | Original spreadsheet on disk                              |
| User sheet     | `source_sheet`    | Worksheet/tab in the spreadsheet                          |
| Canonical col  | `field`           | Defined in manifest; never call this a “column”           |
| Physical col   | column            | B / C / index 0,1,2… in a sheet                           |
| Output workbook| normalized workbook| Written to `output_dir`; includes mapped + normalized data|

Telemetry payloads mirror artifact/run models and reuse these names.

---

## 1. Goal and mental model

Telemetry answers: **“What happened, in what order, with what context?”**

- It is:
  - **Append-only** — a time-ordered stream of small JSON envelopes.
  - **Per-run** — one NDJSON file per engine run.
  - **Configurable** — extra sinks can be plugged in (e.g. message bus).
- It is *not*:
  - A full audit snapshot (that’s `artifact.json`).
  - A durable state store or metrics DB.

The engine writes telemetry via a small set of APIs and abstractions:

- **Data model**: `TelemetryEvent`, `TelemetryEnvelope`.
- **Runtime wiring**: `TelemetryConfig`, `TelemetryBindings`.
- **Output**: `EventSink` implementations (`FileEventSink`, `DispatchEventSink`).
- **Public facade**: `PipelineLogger` (what pipeline and config code use).

---

## 2. Telemetry vs. artifact

The engine produces two complementary outputs:

- **`artifact.json`** — structured, run-level snapshot:
  - Mapping decisions, validation issues, table metadata, notes.
  - Optimized for **post-run inspection and reporting**.

- **`events.ndjson`** — line-based event stream:
  - `run_started`, `pipeline_transition`, `file_processed`,
    `validation_issue`, `run_failed`, etc.
  - Optimized for **streaming**, **log aggregation**, and **near-real-time UI**.

Most data is visible in both, but:

- Artifact is **hierarchical and consolidated**.
- Telemetry is **fine-grained and chronological**.

---

## 3. Data model

### 3.1 TelemetryEvent

An individual event emitted by the engine, modeled in
`ade_engine.schemas.telemetry` (Pydantic).

Conceptual fields:

- `event: str`  
  Short name, e.g. `"run_started"`, `"file_processed"`,
  `"pipeline_transition"`, `"validation_issue"`.
- `level: str`  
  One of `"debug" | "info" | "warning" | "error" | "critical"`.
- `payload: dict[str, Any]`  
  Event-specific data, e.g.:

  ```jsonc
  {
    "event": "file_processed",
    "level": "info",
    "payload": {
      "file": "input.xlsx",
      "table_count": 3
    }
  }
````

The event name and level are always present; the payload is free-form, but
should be **small, self-contained, and JSON-friendly**.

### 3.2 TelemetryEnvelope

Every event is wrapped in an envelope with run context and timestamps.

Modeled as e.g. `TelemetryEnvelope` in `ade_engine.schemas.telemetry`:

* `schema: str`
  Schema tag, e.g. `"ade.telemetry/run-event.v1"`.
* `version: str`
  Version of the telemetry schema.
* `run_id: str`
  The engine’s internal run ID (`RunContext.run_id`).
* `timestamp: str`
  ISO 8601 UTC timestamp of when the event was emitted.
* `metadata: dict[str, Any]`
  Optional subset of `RunContext.metadata` for correlation (artifact does not store these), e.g.:

  * `job_id`
  * `config_id`
  * `workspace_id`
  (These are caller-provided tags; `job_id` refers to a backend job, not an engine concept.)
* `event: TelemetryEvent`

Example envelope (one line in `events.ndjson`):

```json
{
  "schema": "ade.telemetry/run-event.v1",
  "version": "1.0.0",
  "run_id": "run-uuid-1234",
  "timestamp": "2024-01-01T12:34:56Z",
  "metadata": {
    "job_id": "job-abc",
    "config_id": "config-1.2.3"
  },
  "event": {
    "event": "file_processed",
    "level": "info",
    "payload": {
      "file": "input.xlsx",
      "table_count": 3
    }
  }
}
```

---

## 4. Event sinks

### 4.1 EventSink protocol

Internally, sinks implement a minimal interface (conceptual):

```python
class EventSink(Protocol):
    def log(
        self,
        event: str,
        *,
        run: RunContext,
        level: str = "info",
        **payload: Any,
    ) -> None:
        ...
```

Responsibilities:

* Construct `TelemetryEvent` and wrap it in a `TelemetryEnvelope`.
* Decide whether to emit the event (e.g. filter by level).
* Write or forward it to the appropriate backend (file, bus, etc).

### 4.2 FileEventSink

Default sink used by the engine.

* Writes **one JSON envelope per line** to:

  ```text
  <logs_dir>/events.ndjson
  ```

* Behavior:

  * Opens file in append mode.
  * Serializes the envelope to JSON.
  * Writes a single line per event.

* Guarantees:

  * Events are appended in the order they are emitted.
  * If no events are emitted, the file still exists (may be empty).

### 4.3 DispatchEventSink

Composite sink that fans out events to multiple sinks.

* Holds a list of child `EventSink` instances.
* On `log(...)`, forwards the event to each child.
* Typical usage:

  * File + console logs.
  * File + HTTP/queue sink in a worker environment.

---

## 5. TelemetryConfig and bindings

### 5.1 TelemetryConfig

`TelemetryConfig` is passed to `Engine.__init__` and controls how telemetry
behaves for that engine instance.

Conceptual fields:

* `correlation_id: str | None`
  Optional out-of-band correlation ID (e.g., from the worker/job system).
* `min_event_level: str`
  Minimum severity for events to be emitted (e.g. `"info"`).
* `event_sink_factories: list[Callable[[RunContext], EventSink]]`
  Factories to build sinks for each run.

Intent:

* Configure **once** at engine construction.
* Keep **run-specific data** (paths, run_id, metadata) in `RunContext`, not in
  the config.

### 5.2 TelemetryBindings

For each run, the engine creates `TelemetryBindings`:

* Holds:

  * `events: EventSink` — already wired to `<logs_dir>/events.ndjson` and any
    additional sinks.
  * `artifact` sink — for structured notes (see `artifact.json` doc).
* Decorates events with:

  * `run_id`, `metadata`, timestamps, schema tags.

`TelemetryBindings` is attached to `RunContext` (directly or indirectly) and is
used by `PipelineLogger` to emit events and notes.

---

## 6. PipelineLogger

`PipelineLogger` is the **single entry point** that pipeline code and config
scripts should use for logging and telemetry.

### 6.1 API

Conceptually:

```python
class PipelineLogger:
    def note(self, message: str, level: str = "info", **details: Any) -> None: ...
    def event(self, name: str, level: str = "info", **payload: Any) -> None: ...
    def transition(self, phase: str, **payload: Any) -> None: ...
    def record_table(self, table_summary: dict[str, Any]) -> None: ...
```

* `note(...)`

  * Writes a human-friendly note into the artifact’s `notes` list.
  * May also emit a telemetry event (depending on config).
* `event(...)`

  * Emits a structured telemetry event only (`TelemetryEvent`/`TelemetryEnvelope`).
* `transition(...)`

  * Convenience helper that emits a `pipeline_transition` event with:

    * `phase` and extra details (file counts, table counts, etc).
* `record_table(...)`

  * Records table mapping/validation summary into the artifact and may emit a
    telemetry event summarizing the table.

### 6.2 Usage guidelines

* **Engine internals**:

  * Use `transition` at stage boundaries.
  * Use `event` for specific meaningful events.
  * Use `note` for human-readable context in the artifact.
* **Config scripts & hooks**:

  * Prefer `logger.event(...)` for custom structured events (e.g. scoring or
    business-quality metrics).
  * Use `logger.note(...)` for narrative context that should appear in the
    artifact (e.g. “Detected unusual member ID patterns”).

---

## 7. NDJSON output

### 7.1 File location

Telemetry is written to:

```text
<logs_dir>/events.ndjson
```

where `logs_dir` is determined from `RunRequest` / `RunPaths`.

### 7.2 Format guarantees

* Each line is a **single complete JSON object** (a `TelemetryEnvelope`).
* Lines are separated by `\n` with no trailing comma.
* Consumers can treat the file as a standard NDJSON stream.

### 7.3 Example (abridged)

```text
{"schema":"ade.telemetry/run-event.v1","version":"1.0.0","run_id":"run-1",...,"event":{"event":"run_started","level":"info","payload":{...}}}
{"schema":"ade.telemetry/run-event.v1","version":"1.0.0","run_id":"run-1",...,"event":{"event":"pipeline_transition","level":"info","payload":{"phase":"extracting","file_count":1}}}
{"schema":"ade.telemetry/run-event.v1","version":"1.0.0","run_id":"run-1",...,"event":{"event":"file_processed","level":"info","payload":{"file":"input.xlsx","table_count":2}}}
{"schema":"ade.telemetry/run-event.v1","version":"1.0.0","run_id":"run-1",...,"event":{"event":"run_completed","level":"info","payload":{"status":"succeeded"}}}
```

The exact payload shape varies by event name, but all share the same envelope.

---

## 8. Standard events

The engine emits a small, consistent set of event types. Configs may add more,
but should avoid redefining these.

### 8.1 Core lifecycle

* `run_started`
  Emitted once at run start.

  Payload (typical):

  * `engine_version`
  * `config_version`
  * basic input summary (e.g. file count)

* `run_completed`
  Emitted once on successful completion.

  Payload:

  * `status: "succeeded"`
  * `duration_ms`
  * optional row/table counts

* `run_failed`
  Emitted once on failure.

  Payload:

  * `status: "failed"`
  * `error_code` (e.g., `config_error`, `input_error`, `hook_error`, `pipeline_error`, `unknown_error`)
  * `error_stage` (e.g., `initialization`, `load_config`, `extracting`, `mapping`, `normalizing`, `writing_output`, `hooks`)
  * `error_message`

### 8.2 Pipeline transitions

* `pipeline_transition`
  Emitted when the pipeline moves between phases:

  * `"initialization"`
  * `"load_config"`
  * `"extracting"`
  * `"mapping"`
  * `"normalizing"`
  * `"writing_output"`
  * `"completed"`
  * `"failed"`

  Payload (typical):

  * `phase`
  * optional counters (e.g. `file_count`, `table_count`)

### 8.3 File and table events

* `file_discovered`
  Emitted when a source file is discovered (optional).

* `file_processed`
  Emitted after a file has been fully processed.

  Payload:

  * `file`
  * `table_count`

* `table_detected`
  Emitted after a `RawTable` is constructed.

  Payload:

  * `file`
  * `sheet`
  * `header_row_index`
  * `data_row_count`

### 8.4 Validation and quality

* `validation_issue`
  Optional per-issue or per-row event.

  Payload (typical):

  * `file`
  * `sheet`
  * `row_index`
  * `field`
  * `code`
  * `severity`

Configs may:

* Emit their own domain-specific events (e.g. `quality_score_computed`).
* Use these standard events to align with ADE backend expectations.

---

## 9. Consumption by ADE backend

Typical backend workflows:

* **Batch ingestion**:

  * Parse `events.ndjson` after run completion.
  * Derive metrics (e.g. total rows processed, error rates).
  * Store data in a log index or metrics system.

* **Streaming / UI**:

  * Tail `events.ndjson` (or equivalent stream in workers).
  * Push events into a websocket or UI log.
  * Show progress as phases change and files/tables are processed.

The engine does not know where or how events are consumed; it just writes
envelopes to the configured sinks.

---

## 10. Best practices and extensibility

### 10.1 For engine maintainers

* Keep the **set of standard event names small and stable**.
* When changing envelope or payload structure:

  * Prefer additive changes.
  * For breaking changes, bump the telemetry schema `version`.
* Ensure `events.ndjson` is always created and valid, even on early failures.

### 10.2 For config authors

* Use `logger.event(...)` for custom events instead of ad-hoc printing.
* Keep payloads:

  * Small,
  * JSON-serializable,
  * Stable (avoid putting huge blobs or entire rows in telemetry).

### 10.3 For backend integrators

* Treat `events.ndjson` as a **log source**, not a permanent store.
* Use:

  * Artifact for detailed, structured reporting.
  * Telemetry for progress, alerts, and coarse metrics.
* When adding custom sinks (via `TelemetryConfig`):

  * Ensure they are **non-blocking** or have appropriate backpressure.
  * Handle network/IO errors gracefully (do not crash the run).

With these conventions, telemetry stays predictable, useful, and easy to
consume without complicating the core engine.
