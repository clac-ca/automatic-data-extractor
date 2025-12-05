# Telemetry Events (`ade.event/v1`)

The engine’s external contract is **telemetry + normalized outputs**. Every
observable action is emitted as an `AdeEvent` envelope and written to
`logs/events.ndjson` by the default `FileEventSink`. Downstream systems derive
run summaries and status from this stream.

## 1. Event envelope

Envelope class: `AdeEvent` in `schemas/telemetry.py`.

- `type`: string, e.g., `console.line`, `engine.start`, `engine.table.summary`, `engine.complete`.
- `created_at`: timestamp (UTC).
- `sequence`: optional, monotonic per run **when assigned by the ADE API**; engine leaves unset.
- `workspace_id`, `configuration_id`, `run_id`: propagated from `RunRequest.metadata` when provided.
- `payload`: type-specific fields (see below).

Events are serialized one per line (NDJSON). File order matches emission order;
ordering-sensitive consumers should still use `sequence` once the API replays
and stamps the stream.

## 2. Default sink and location

- Default sink: `FileEventSink` from `TelemetryConfig.build_sink`.
- Location: `<logs_dir>/events.ndjson`.
- Filtering: `min_event_level` on `TelemetryConfig` (default `info`) suppresses lower-level events.

You can add additional sinks (IPC/HTTP/etc.) via `TelemetryConfig.event_sink_factories`.

## 3. Event types emitted by the engine

- `console.line` — produced by the run logger via `TelemetryLogHandler`; payload has `scope:"run"`, `stream`, `level`, `message`, optional `logger`/`engine_timestamp`.
- `engine.start` — emitted at the beginning of `Engine.run` with `status:"running"`, `engine_version`, and optional `config_version`.
- `engine.phase.start` / `engine.phase.complete` — coarse progress markers when pipeline stages begin/end (used for “extracting”, “mapping”, “normalizing”, “writing_output”, etc.).
- `engine.detector.row.score` — summary per extracted table: header row index, data row range, thresholds, trigger row scores/contributions, and a small value sample.
- `engine.detector.column.score` — summary per manifest field per table: chosen column (or unmapped), threshold, and top-N candidate scores with contribution breakdowns.
- `engine.table.summary` — one per normalized table; payload uses the `TableSummary` schema (counts, fields, columns, validation, details) defined in `schemas/summaries.py`.
- `engine.sheet.summary` / `engine.file.summary` — aggregated summaries across tables within a sheet or file.
- `engine.run.summary` — authoritative run summary emitted before completion (payload = `RunSummary`).
- `engine.validation.summary` — aggregated validation counts when issues exist.
- `engine.validation.issue` — optional per-issue events for fine-grained debugging.
- `engine.complete` — terminal status; payload includes `status`, optional `failure` block, `output_path`, and `processed_file`.
- `config.*` — optional custom events emitted by config code via the provided `ConfigEventEmitter`.

## 4. Correlation and metadata

`RunRequest.metadata` is used to populate `workspace_id`/`configuration_id`
fields on events. Additional payload data can be passed through
`EventEmitter.custom("type_suffix", **payload)` or human logs emitted via the run `logger`.

## 5. Consuming events

- Treat `events.ndjson` as the single source of truth for run telemetry.
- The engine now emits hierarchical summaries (`engine.table.summary`, `engine.sheet.summary`, `engine.file.summary`, `engine.run.summary`); consumers should persist/use the run-level payload instead of recomputing from the log.
- In streaming scenarios, tail `events.ndjson` while the engine runs, or plug
  in a custom sink; the ADE API replays these events, stamps `event_id`/`sequence`, and streams them via SSE.

## 6. Emitting custom telemetry from hooks

Hooks receive `logger: logging.Logger` and a `ConfigEventEmitter`. Use:

- `logger.debug/info/warning/error(...)` for human-friendly console lines (bridged to `console.line`).
- `event_emitter.custom("type_suffix", **payload)` for structured **config.*** events when you need your own checkpoints.
- `event_emitter.phase_started("phase", **details)` for coarse config progress markers if desired.

The engine already emits `engine.*` events for phases, detector scores, validation, summaries, and completion. Custom config events should be sparse and domain-specific.
