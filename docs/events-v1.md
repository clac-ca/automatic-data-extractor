# ADE Events v1 – Engine Frames → API Envelope

ADE now standardizes run/build telemetry on a single canonical stream owned by the API. The engine emits lightweight frames to stdout; the API ingests them, stamps IDs/sequence, persists `events.ndjson`, and streams to clients (SSE/NDJSON download).

## Wire formats

### Engine frame (stdout)
`apps/ade-engine/src/ade_engine/schemas/events/v1/frame.py`

```jsonc
{
  "schema_id": "ade.engine.events.v1",
  "type": "engine.table.summary",
  "event_id": "uuid",          // engine-local UUID
  "created_at": "2025-01-01T00:00:00Z",
  "payload": { /* engine payload */ }
}
```

- Strict (`extra="forbid"`); payload is a dict.
- Only emitted to stdout (stderr is reserved for human-readable logs).
- `event_id` is preserved as `origin_event_id` by the API.

### API envelope (canonical)
`apps/ade-api/src/ade_api/schemas/events/v1/envelope.py`

```jsonc
{
  "schema_id": "ade.events.v1",
  "type": "engine.table.summary",
  "event_id": "evt_<uuid7>",    // stamped by API
  "sequence": 42,               // monotonic per run
  "created_at": "2025-01-01T00:00:00Z",
  "source": "engine",           // or "api"
  "workspace_id": "<uuid>",
  "configuration_id": "<uuid>",
  "run_id": "<uuid>",
  "build_id": "<uuid|null>",
  "origin_event_id": "<uuid|null>",
  "payload": { /* validated payload */ }
}
```

- Strict envelope; payloads are typed where stabilized (run.*, console.line, engine.* summaries).
- Persisted as `logs/events.ndjson` by the API dispatcher and streamed via SSE/NDJSON download.

## Flow (happy path)
1. API creates run → emits `run.queued`/`run.start` (source="api").
2. API spawns engine with `stdout=PIPE`, `stderr=PIPE`.
3. Engine writes `EngineEventFrameV1` lines to stdout; stderr lines become `console.line` events.
4. API parses frames → `AdeEventV1` with `origin_event_id`, stamps `event_id` + `sequence`, persists, and streams.
5. API emits `run.complete` with a RunResource snapshot when execution finishes.

## Naming & versioning
- `schema_id` discriminators: `ade.engine.events.v1` (frames) and `ade.events.v1` (canonical).
- Event types are dot-delimited (`run.complete`, `console.line`, `engine.phase.start`).
- New payload shapes should be added as versioned event types (introduce new `type` or payload fields; avoid breaking changes).

## Testing expectations
- Engine stdout contains only valid frames; flushing per line keeps UI responsive.
- API dispatcher enforces monotonic `sequence` per run and preserves `origin_event_id` for traceability.
- Frontend consumes only the API envelope; resume/replay uses `sequence` and `event_id`.
