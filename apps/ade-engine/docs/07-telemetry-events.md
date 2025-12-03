# Telemetry Events (`ade.event/v1`)

The engine’s external contract is **telemetry + normalized outputs**. Every
observable action is emitted as an `AdeEvent` envelope and written to
`logs/events.ndjson` by the default `FileEventSink`. Downstream systems derive
run summaries and status from this stream.

## 1. Event envelope

Envelope class: `AdeEvent` in `schemas/telemetry.py`.

- `type`: string, e.g., `console.line`, `run.started`, `run.table.summary`, `run.completed`.
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
- `run.started` — emitted at the beginning of `Engine.run` with `status:"in_progress"` and `engine_version`.
- `run.phase.started` — progress markers emitted via `EventEmitter.phase_started("extracting" | "mapping" | "normalizing" | "writing_output" | ...)`.
  - **The engine does not emit `run.phase.completed` today.**
- `run.row_detector.score` — summary per extracted table: header row index, data row range, thresholds, trigger row scores/contributions, and a small value sample.
- `run.column_detector.score` — summary per manifest field per table: chosen column (or unmapped), threshold, and top-N candidate scores with contribution breakdowns.
- `run.table.summary` — one per normalized table; payload includes source file/sheet, table_index, row_count/column_count, mapping (mapped + unmapped columns), validation breakdowns (totals/by_severity/by_code/by_field), unmapped_column_count, header/data row indices.
- `run.validation.summary` — aggregated validation counts when issues exist.
- `run.validation.issue` — optional per-issue events for fine-grained debugging.
- `run.error` — structured error context (`stage`, `code`, `message`, optional `phase`/`details`) when exceptions are mapped to `RunError`.
- `run.completed` — terminal status; payload includes `status`, `output_paths`, `processed_files`, `events_path`, and optional `error` info.

## 4. Correlation and metadata

`RunRequest.metadata` is used to populate `workspace_id`/`configuration_id`
fields on events. Additional payload data can be passed through
`EventEmitter.custom("type_suffix", **payload)` or human logs emitted via the run `logger`.

## 5. Consuming events

- Treat `events.ndjson` as the single source of truth for run telemetry.
- Build `RunSummaryV1` by replaying events; see `12-run-summary-and-reporting.md`.
- In streaming scenarios, tail `events.ndjson` while the engine runs, or plug
  in a custom sink; the ADE API replays these events, stamps `event_id`/`sequence`, and streams them via SSE.

## 6. Emitting custom telemetry from hooks

Hooks receive `logger: logging.Logger` and `event_emitter: EventEmitter`. Use:

- `logger.debug/info/warning/error(...)` for human-friendly console lines (bridged to `console.line`).
- `event_emitter.custom("type_suffix", **payload)` for structured run events.
- `event_emitter.phase_started("phase", **details)` for coarse progress markers.
- `event_emitter.table_summary(table)` to emit standardized table summaries.
- `event_emitter.validation_issue(**payload)` / `event_emitter.validation_summary(issues)` for validation telemetry.

Hooks do not access sinks directly; these two primitives are the supported surface.
