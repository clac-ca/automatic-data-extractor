# 11 – ADE event model (current implementation)

This chapter describes the **actual** ADE event model as implemented in
`ade_engine` and consumed by `ade-api` for streaming and replay.

---

## 1. Envelope

Class: `AdeEvent` (`apps/ade-engine/src/ade_engine/schemas/telemetry.py`)

- `type`: string (e.g., `console.line`, `run.started`, `run.table.summary`, `run.completed`)
- `event_id`: optional string; **set by ade-api**, not by the engine
- `created_at`: timestamp (UTC)
- `sequence`: optional int; **set by ade-api** for run-scoped streams
- `source`: optional string (`engine`, `api`, etc.)
- `workspace_id`, `configuration_id`, `run_id`, `build_id`: optional strings (engine fills from `RunRequest.metadata` when provided)
- `payload`: type-specific object or dict

Engine writes NDJSON lines without `event_id`/`sequence`; ade-api re-envelops
and stamps those fields before persisting/streaming to clients.

---

## 2. Event catalog (engine-origin)

- **`console.line`** — emitted via `PipelineLogger.note`
  - Payload: `scope:"run"`, `stream:"stdout"|"stderr"`, `level` (default `info`), `message`, optional `logger`, `engine_timestamp`.
- **`run.started`** — emitted once per engine invocation with `status:"in_progress"` and `engine_version`.
- **`run.phase.started`** — optional progress markers (`extracting`, `mapping`, `normalizing`, `writing_output`, etc.) emitted via `PipelineLogger.pipeline_phase`.
  - The engine **does not emit `run.phase.completed`** today.
- **`run.table.summary`** — one per normalized table; includes source file/sheet, table_index, row/column counts, mapping (`mapped_columns` + `unmapped_columns`), `mapped_fields` summary, `unmapped_column_count`, validation breakdowns (`total`, `by_severity`, `by_code`, `by_field`), and header/data row indices.
- **`run.validation.summary`** — aggregated validation counts (emitted when issues exist).
- **`run.validation.issue`** — optional per-issue events for debugging.
- **`run.error`** — structured error context (`stage`, `code`, `message`, optional `phase`/`details`) when exceptions are mapped to `RunError`.
- **`run.completed`** — terminal status with `status`, `output_paths`, `processed_files`, `events_path`, and optional `error` info.

Build events are produced by ade-api (not the engine) and re-enveloped through
the ade-api dispatcher; see the backend docs for build streaming.

---

## 3. Storage and streaming

- Engine writes `events.ndjson` under `<logs_dir>/events.ndjson` via
  `FileEventSink` (configured in `TelemetryConfig`).
- ade-api tails the engine-written `events.ndjson`, re-emits events through
  `RunEventDispatcher` (stamping `event_id`/`sequence`), and persists them to
  `<runs_root>/<run_id>/logs/events.ndjson` for replay and SSE streaming.
- Build-only SSE streams (ade-api) do **not** persist events unless they are
  part of a run stream.

---

## 4. Guidance for contributors

- Prefer adding new, narrow event types over overloading existing payloads.
- If you add new payload fields, keep them additive and update:
  - `schemas/telemetry.py` (payload models)
  - `apps/ade-api` summary builders/dispatchers as needed
  - Frontend reducers if they consume the new shape
- Avoid introducing engine-side `sequence`/`event_id`; let ade-api own ordering
  and identifiers for streamed runs.

For detailed telemetry usage and the frontend/backend integration, see
`07-telemetry-events.md`, `apps/ade-api` event dispatcher docs, and the
frontend streaming guide.
