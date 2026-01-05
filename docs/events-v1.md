# ADE Events v1 – EventRecord NDJSON logs

ADE standardises run/build telemetry as **EventRecord** lines written by the worker. The engine emits NDJSON `EventRecord` objects to **stderr**; the **worker** captures and appends them to `events.ndjson` for each build or run. The API serves those logs over JSON, NDJSON, and SSE.

## EventRecord envelope

Top-level keys match the engine schema; the worker adds optional context inside `data`:

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
- **Engine NDJSON stderr** — primary source; each line is a JSON object with an `event` field.
- **Worker-origin events** — orchestration emits `run.*`, `build.*`, and `console.line` records using the same envelope.
- **Console fallback** — non-JSON stdout/stderr lines are wrapped as `console.line` events with `data.scope` = `run` or `build`.

## Flow (happy path)
1. API creates `builds`/`runs` rows (status = `queued`).
2. Worker claims a build or run (lease + heartbeat) and writes `events.ndjson` as it executes.
3. Worker updates status (`ready`, `succeeded`, `failed`) on completion.
4. API streams the NDJSON logs over SSE or returns paged event lists.

## Persistence, replay, and SSE
- **Run logs**: `<runs_root>/<workspace>/<run_id>/logs/events.ndjson` (one stream per run).
- **Build logs**: `<venvs_root>/<workspace>/<configuration>/<build>/logs/events.ndjson`.
- SSE frames always include `id: <sequence>`; if the event already has a numeric `sequence`, that value is reused. Otherwise, the API assigns a monotonic counter as it tails the file.
- Replay reads the NDJSON log in order, skips entries until the cursor (`Last-Event-ID` or `after_sequence`) is reached, then continues live on the same stream.

## Naming & versioning
- Envelope name stays `EventRecord`; add new fields under `data` to avoid breaking changes.
- `event` values are dot-delimited; prefer new event names over changing payload structure.
