# Telemetry Events (`events.ndjson`)

This document describes the **telemetry event system** used by the ADE engine:

- how events are modeled and written to `events.ndjson`,
- how they relate to `artifact.json` and run summaries,
- and which `run.*` event types the engine emits.

This focuses on **engine-side** telemetry. For the unified ADE event envelope
and how builds / runs are streamed by the API, see
`11-ade-event-model.md`. For run summaries (what goes into the `runs` table and
front-end reporting), see `12-run-summary-and-reporting.md`.

## Terminology

| Concept        | Term in code        | Notes                                                     |
| -------------- | ------------------- | --------------------------------------------------------- |
| Run            | `run`               | One call to `Engine.run()` or one CLI invocation         |
| Config package | `config_package`    | Installed `ade_config` package for this run              |
| Config version | `manifest.version`  | Version declared by the config package manifest          |
| Build          | build               | Virtual environment built for a specific config version  |
| User data file | `source_file`       | Original spreadsheet on disk                             |
| User sheet     | `source_sheet`      | Worksheet/tab in the spreadsheet                         |
| Canonical col  | `field`             | Defined in manifest; never call this a “column”          |
| Physical col   | column              | B / C / index 0,1,2… in a sheet                          |
| Output workbook| normalized workbook | Written to `output_dir`; includes mapped + normalized data |

Telemetry payloads reuse these names for consistency with runtime and
artifact docs.

---

## 1. Telemetry vs artifact vs run summary

The engine produces two low-level outputs:

1. **`artifact.json`** – hierarchical snapshot:

   - mapping decisions (per table),
   - validation issues,
   - notes,
   - run-level status.

2. **`events.ndjson`** – line-oriented event stream:

   - `run.started`, `run.pipeline.progress`, `run.table.summary`,
     `run.completed`, etc.

The ADE API then derives a **run summary** object from these artifacts:

- ingests `artifact.json` + `events.ndjson`,
- aggregates metrics (rows, issues, mapping quality),
- attaches the summary to the `run.completed` event payload,
- persists summary into the `runs` table for BI.

The engine itself knows nothing about SQL or run summaries; it just writes:

- `artifact.json` (see `06-artifact-json.md`), and
- `events.ndjson` (this document).

---

## 2. Envelope: `ade.event/v1`

All engine telemetry events are written using the **unified ADE event
envelope**:

```jsonc
{
  "type": "run.pipeline.progress",
  "object": "ade.event",
  "schema": "ade.event/v1",
  "version": "1.0.0",
  "created_at": "2025-11-26T12:00:03Z",

  "workspace_id": null,
  "configuration_id": null,
  "run_id": "run_123",
  "build_id": null,

  "run": { ... },
  "build": null,
  "env": null,
  "validation": null,
  "execution": null,
  "output_delta": null,
  "log": null,
  "error": null
}
```

Notes:

* `type` is the **primary discriminator** (e.g. `"run.started"`,
  `"run.pipeline.progress"`, `"run.table.summary"`, `"run.completed"`).

* `object`, `schema`, and `version` are constant:

  * `object = "ade.event"`
  * `schema = "ade.event/v1"`
  * `version` evolves semantically (e.g. `"1.0.0"`).

* `created_at` is an ISO 8601 UTC timestamp (when the event was emitted).

* Correlation context:

  * `run_id` is always set for engine events.
  * `workspace_id` / `configuration_id` / `build_id` may be `null` on the
    engine side; the API often fills them when streaming.

The envelope shape is shared with API-level events (build events, wrapper
run events). See `11-ade-event-model.md` for a full catalog.

---

## 3. Event sinks

### 3.1 EventSink protocol

Inside the engine, sinks implement a minimal interface:

```python
class EventSink(Protocol):
    def log(
        self,
        *,
        type: str,
        run: RunContext,
        level: str = "info",
        **payload: Any,
    ) -> None:
        ...
```

Responsibilities:

* build a `ade.event/v1` envelope:

  * set `type`, `object`, `schema`, `version`,
  * set `run_id` and other context from `RunContext`,
  * attach the payload under the correct namespace (`run`, `validation`,
    `output_delta`, `log`, etc.),

* serialize to JSON,

* write or forward the event.

### 3.2 FileEventSink

Default sink used by the engine:

* writes one **JSON object per line** to:

  ```text
  <logs_dir>/events.ndjson
  ```

* opens the file in append mode,

* writes events in the order they are emitted.

Guarantees:

* `events.ndjson` exists for every run (possibly empty if no events).
* Each line is a complete JSON envelope.

### 3.3 DispatchEventSink

Optional composite sink that fans out events to multiple sinks:

* holds a list of `EventSink` instances,
* forwards every event to each child sink,
* enables setups like “file + console” or “file + message bus”.

---

## 4. PipelineLogger

`PipelineLogger` is the **only thing** pipeline code and config scripts should
use to emit telemetry and artifact notes.

Conceptual API:

```python
class PipelineLogger:
    def note(self, message: str, level: str = "info", **details: Any) -> None: ...
    def event(self, name: str, level: str = "info", **payload: Any) -> None: ...
    def transition(self, phase: str, **payload: Any) -> None: ...
    def record_table(self, table_summary: dict[str, Any]) -> None: ...
```

* `note`

  * Appends a human-friendly note to the artifact’s `notes` array.
  * Optionally emits a `run.note` telemetry event (depending on config).

* `event(name, ...)`

  * Emits a structured event with `type = "run." + name` and the given payload.
  * Does **not** directly touch the artifact.

* `transition(phase, ...)`

  * Convenience wrapper to emit `run.pipeline.progress` events.

* `record_table(table_summary)`

  * Writes table summary data into `artifact.json`.
  * May also emit a `run.table.summary` event with a compact payload.

Engine internals use `PipelineLogger`. Config scripts and hooks receive the
same logger and should use it instead of `print`.

---

## 5. NDJSON output

### 5.1 File location

Telemetry is written to:

```text
<logs_dir>/events.ndjson
```

Where `logs_dir` comes from `RunRequest`/`RunPaths`.

### 5.2 Format

* Each line is one JSON envelope (`ade.event/v1`).
* Lines are separated by `\n`.
* There’s no trailing comma or array wrapper.

Example (abridged):

```text
{"type":"run.started","object":"ade.event","schema":"ade.event/v1","version":"1.0.0","run_id":"run_1",...,"run":{"engine_version":"0.2.0"}}
{"type":"run.pipeline.progress","object":"ade.event","schema":"ade.event/v1","version":"1.0.0","run_id":"run_1",...,"run":{"phase":"extracting","file_count":1}}
{"type":"run.table.summary","object":"ade.event","schema":"ade.event/v1","version":"1.0.0","run_id":"run_1",...,"output_delta":{"kind":"table_summary","table":{"source_file":"input.xlsx","source_sheet":"Sheet1","table_index":0,"row_count":100,"validation_issue_counts":{"error":2,"warning":5}}}}
{"type":"run.completed","object":"ade.event","schema":"ade.event/v1","version":"1.0.0","run_id":"run_1",...,"run":{"engine_status":"succeeded","exit_code":0}}
```

The ADE API typically **tails** this file while the run is live and forwards
events to clients.

---

## 6. Standard engine `run.*` events

The engine emits a compact set of `run.*` events; configs may emit additional
events via `logger.event()`.

### 6.1 `run.started`

Emitted once, near the start of `Engine.run`.

```jsonc
{
  "type": "run.started",
  "run": {
    "engine_version": "0.2.0",
    "config_version": "3.1.0",
    "config_schema": "ade.manifest/v1",
    "input_file_count": 1
  }
}
```

Use cases:

* “Run has begun” indicator.
* Showing engine and config versions in a stream UI.

### 6.2 `run.pipeline.progress`

Emitted at phase transitions:

* `"initialization"`
* `"load_config"`
* `"extracting"`
* `"mapping"`
* `"normalizing"`
* `"writing_output"`
* `"hooks"`
* `"completed"`
* `"failed"`

Example:

```jsonc
{
  "type": "run.pipeline.progress",
  "run": {
    "phase": "extracting",
    "file_count": 1
  }
}
```

Payload may include small counters (files, tables, rows examined so far).

### 6.3 `run.table.summary`

Emitted once per completed normalized table:

```jsonc
{
  "type": "run.table.summary",
  "output_delta": {
    "kind": "table_summary",
    "table": {
      "source_file": "input.xlsx",
      "source_sheet": "Sheet1",
      "table_index": 0,
      "row_count": 123,
      "validation_issue_counts": {
        "error": 3,
        "warning": 5
      }
    }
  }
}
```

This provides incremental visibility into per-table quality as the run
progresses.

### 6.4 `run.note`

Optional, emitted when the engine or configs record a notable event that should
be visible in both `artifact.json` and the event stream:

```jsonc
{
  "type": "run.note",
  "run": {
    "level": "warning",
    "message": "Empty table detected",
    "details": {
      "source_file": "input.xlsx",
      "source_sheet": "Sheet2"
    }
  }
}
```

`details` should remain small and structured.

### 6.5 `run.completed` / `run.failed` (engine view)

The engine emits a terminal event when the pipeline finishes:

```jsonc
{
  "type": "run.completed",
  "run": {
    "engine_status": "succeeded",
    "exit_code": 0,
    "duration_ms": 9000
  }
}
```

On failure:

```jsonc
{
  "type": "run.failed",
  "run": {
    "engine_status": "failed",
    "exit_code": 1
  },
  "error": {
    "code": "config_error",
    "stage": "load_config",
    "message": "Unable to import ade_config",
    "details": {
      "exception_type": "ImportError",
      "exception_message": "No module named 'ade_config'"
    }
  }
}
```

The API typically wraps these with its own `run.completed` events containing
high-level status, artifact/events paths, and the aggregated **run summary**
object.

---

## 7. Custom events from configs

Config code and hooks may emit domain-specific events:

```python
logger.event(
    "quality_score_computed",
    level="info",
    score=0.97,
    rows=1230,
)
```

This becomes:

```jsonc
{
  "type": "run.quality_score_computed",
  "run": {
    "level": "info",
    "score": 0.97,
    "rows": 1230
  }
}
```

Guidelines:

* Keep payloads **small and JSON-friendly**.
* Use stable event names; prefer `run.<noun_or_verb>` patterns.
* Avoid dumping whole rows or giant strings in the payload; reflect structured
  metrics instead.

---

## 8. Consumption by ADE API

The ADE API typically:

1. Tails `events.ndjson` while the engine is running.
2. Forwards envelopes directly to clients (WebSocket / SSE).
3. On run completion, reads `artifact.json` and `events.ndjson` and:

   * computes a `run.summary` object (see `12-run-summary-and-reporting.md`),
   * attaches it to a **final** `run.completed` API event,
   * persists run metadata + summary into the `runs` table.

Engine code remains unaware of this; its job is only to write a clean,
versioned NDJSON stream and artifact.

---

## 9. Extensibility and versioning

The telemetry format is versioned via:

* `schema = "ade.event/v1"`,
* `version = "1.0.0"`.

Additive changes:

* new event types (e.g. `run.validation.issue.delta`),
* new optional payload fields.

Breaking changes:

* changing payload shape for an existing `type`,
* changing semantics of existing fields.

Breaking changes require either bumping `schema` (e.g. `"ade.event/v2"`) or at
least a major bump and a coordinated migration. Engine and API should evolve
telemetry together with explicit tests.

Use `11-ade-event-model.md` as the canonical reference for the global ADE
event space; this document stays focused on **engine-side emission**.
