# ADE Events v1 – Unified EventRecord streams

ADE standardises run/build telemetry on a single canonical stream owned by the API. The engine emits NDJSON `EventRecord` objects to **stderr**; the API ingests them, enriches context, persists `events.ndjson`, and fans out over SSE.

## EventRecord envelope

Top-level keys match the engine schema; the API only adds optional context inside `data`:

```jsonc
{
  "event_id": "uuid",               // engine-supplied or generated
  "engine_run_id": "uuid",          // engine correlation
  "timestamp": "2025-01-01T00:00:00Z",
  "level": "info",
  "event": "engine.table.summary",  // namespaced event name
  "message": "Workbook processing started",
  "data": {
    "jobId": "<run_id>",
    "workspaceId": "<workspace_id>",
    "buildId": "<build_id>",
    "configurationId": "<configuration_id>",
    "...": "source-specific payload"
  },
  "error": { "...": "optional" }
}
```

- Context (`jobId`, `workspaceId`, `buildId`, `configurationId`) is merged into `data` when present.
- `event` names are dot-delimited (`run.complete`, `build.start`, `engine.phase.start`, `console.line`).

## Sources
- **Engine NDJSON stderr** – primary source; each line is a JSON object with an `event` field.
- **API-origin events** – orchestration emits `run.*`, `build.*`, and `console.line` records using the same envelope.
- **Console fallback** – non-JSON stdout/stderr lines are wrapped as `console.line` events with `data.scope` = `run` or `build`.

## Flow (happy path)
1. API creates a `RunEventStream` for `<runs_root>/<workspace>/<run_id>/logs/events.ndjson`.
2. API emits `run.queued`; runs remain queued while builds are pending.
3. If a build is required, `BuildsService.stream_build` emits `build.*` + `console.line scope=build` events **into the same stream** before engine events.
4. API spawns the engine with NDJSON stderr; each parsed line becomes an EventRecord, enriched with run/build/workspace IDs, persisted, and streamed to subscribers with server-generated SSE IDs.
5. API emits `run.complete` once supervision finishes (success, failure, or cancellation).

## Persistence, replay, and SSE
- **Run logs**: `<runs_root>/<workspace>/<run_id>/logs/events.ndjson` (single canonical stream per run).
- **Build-only logs**: `<venvs_root>/<workspace>/<configuration>/<build>/logs/events.ndjson` reuse the same EventRecord format.
- SSE frames always prefix `id: <string>`; the API assigns a monotonically increasing counter per stream and uses it for `Last-Event-ID` resume.
- Replay reads the NDJSON log in order, skips entries until the SSE cursor (`Last-Event-ID`) is reached, then continues live on the same stream.

## Naming & versioning
- Envelope name stays `EventRecord`; add new fields under `data` to avoid breaking changes.
- `event` values are dot-delimited; prefer new event names over changing payload structure.
