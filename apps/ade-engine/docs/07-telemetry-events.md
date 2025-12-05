# Telemetry Events (`ade.engine.events.v1` → `ade.events.v1`)

The engine’s external contract is **telemetry + normalized outputs**. Every
observable action is emitted as an **EngineEventFrameV1** NDJSON line to stdout
(`ade_engine/schemas/events/v1/frame.py`). The ADE API ingests those frames,
stamps `event_id` + `sequence`, and persists the canonical run log (`ade.events.v1`)
for replay/streaming.

## 1. Event envelope

Frame class: `EngineEventFrameV1` in `schemas/events/v1/frame.py`.

- `schema_id`: `"ade.engine.events.v1"` (discriminator for stdout parsing).
- `type`: string, e.g., `console.line`, `engine.start`, `engine.table.summary`, `engine.complete`.
- `created_at`: timestamp (UTC).
- `event_id`: UUID (engine-local traceability).
- `payload`: type-specific fields (see below).

Payloads are emitted from the producing layer without extra enrichment or filesystem probing; when paths are present they are kept run-relative to the run directory.

Frames are serialized one per line (NDJSON). Ordering is the emission order; the
API will re-envelope frames as `ade.events.v1` (via `schema_id`) and apply monotonic `sequence`
per run.

## 2. Default sink and location

- Default sink: `StdoutFrameSink` from `TelemetryConfig.build_sink` (writes to stdout).
- Optional: `FileEventSink` can be injected for tests/local debugging to write `<logs_dir>/events.ndjson`.
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

`RunRequest.metadata` is used to populate correlation IDs on API-enveloped
events. Additional payload data can be passed through
`EventEmitter.custom("type_suffix", **payload)` or human logs emitted via the run
`logger`.

## 5. Consuming events

- Treat the API-written `events.ndjson` as the single source of truth for run telemetry (API wraps engine frames).
- The engine emits hierarchical summaries (`engine.table.summary`, `engine.sheet.summary`, `engine.file.summary`, `engine.run.summary`); consumers should persist/use the run-level payload instead of recomputing from the log.
- In streaming scenarios, read stdout frames directly or attach a custom sink, but prefer consuming the API SSE/NDJSON endpoints for canonical ordering and IDs.

## 6. Emitting custom telemetry from hooks

Hooks receive `logger: logging.Logger` and a `ConfigEventEmitter`. Use:

- `logger.debug/info/warning/error(...)` for human-friendly console lines (bridged to `console.line`).
- `event_emitter.custom("type_suffix", **payload)` for structured **config.*** events when you need your own checkpoints.
- `event_emitter.phase_started("phase", **details)` for coarse config progress markers if desired.

The engine already emits `engine.*` events for phases, detector scores, validation, summaries, and completion. Custom config events should be sparse and domain-specific.
