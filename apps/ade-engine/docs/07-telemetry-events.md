# Telemetry Events (`ade.event/v1`)

The engine’s external contract is now **telemetry-only**: every observable
action is emitted as an `AdeEvent` envelope and written to `logs/events.ndjson`
by the default `FileEventSink`. Downstream systems derive run summaries and
status from this stream.

## 1. Event envelope

All events use the shared `ade.event/v1` schema (`AdeEvent` in
`schemas/telemetry.py`):

- `type`: string, e.g., `run.started`, `run.table.summary`, `run.completed`.
- `created_at`: timestamp (UTC).
- `workspace_id`, `configuration_id`, `run_id`: propagated from `RunRequest.metadata` when provided.
- `run`, `env`, `execution`, `output_delta`, `log`, `error`, etc.: optional payload sections keyed by event type.

Events are serialized one per line (NDJSON). Consumers must not assume ordering
beyond `created_at` monotonicity.

## 2. Default sink and location

- Default sink: `FileEventSink` created by `TelemetryConfig.build_sink`.
- Location: `<logs_dir>/events.ndjson`.
- Level filtering: `min_event_level` on `TelemetryConfig` (default: `info`).

You can add additional sinks (e.g., streaming over IPC or HTTP) by supplying
`event_sink_factories` to `TelemetryConfig`.

## 3. Event types emitted by the engine

- `run.started` — emitted once per run at the beginning; includes `engine_version` and optional metadata.
- `run.pipeline.progress` — phase transitions: `extracting`, `mapping`, `normalizing`, `writing_output`.
- `run.table.summary` — per normalized table; includes:
  - source file/sheet/table_index
  - row_count
  - mapped_fields (field, score, required/satisfied flags)
  - unmapped_column_count and unmapped column descriptors
  - validation breakdowns (totals, by severity/code/field)
- `run.completed` — terminal status; includes `status`, `output_paths`, `processed_files`, and optional error payload.
- `run.console` — freeform console lines emitted via `PipelineLogger.note` (stdout/stderr-style).
- `run.validation.issue.delta` — optional validation deltas emitted by transforms/validators.

## 4. Correlation and metadata

`RunRequest.metadata` is copied into event payloads as `workspace_id` and
`configuration_id` (when present). Additional metadata can be attached via the
`run_payload` argument on `PipelineLogger.event`/`note`.

## 5. Consuming events

- Treat `events.ndjson` as the single source of truth for run telemetry.
- Build run summaries (`ade.run_summary/v1`) by replaying events; see
  `12-run-summary-and-reporting.md` for the aggregation model.
- For streaming scenarios, tail `events.ndjson` while the engine runs, or plug
  in a streaming sink via `TelemetryConfig`.

## 6. Emitting custom telemetry from hooks

Hooks receive a `logger: PipelineLogger`. Use:

- `logger.note("message", level="info", **details)` for human-friendly console lines.
- `logger.pipeline_phase("phase", **details)` for custom progress.
- `logger.record_table(table)` to emit the standardized table summary event.
- `logger.validation_issue(**payload)` to emit validation deltas.

Hooks no longer receive direct access to event sinks or artifacts; the logger
is the supported surface for emitting telemetry.
