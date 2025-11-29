# 050 - ADE API Implementation (Current)

Reference for how the unified run/build streaming system is implemented in ade-api.

---

## 1. Core components

- **Envelope + payloads**: `apps/ade-engine/src/ade_engine/schemas/telemetry.py`
- **Dispatcher + storage**: `apps/ade-api/src/ade_api/features/runs/event_dispatcher.py`
  - `RunEventDispatcher.emit(...)` assigns `event_id` (`evt_<ulid>`), `sequence`, timestamps, and writes to NDJSON via `RunEventStorage.append`.
  - `RunEventStorage.events_path` → `<runs_root>/<workspace_id>/<run_id>/logs/events.ndjson` (created if missing).
  - `RunEventLogReader.iter(...)` replays persisted events with optional `after_sequence`.
  - `subscribe(run_id)` returns `RunEventSubscription` (async iterator over live events).

- **Run orchestration**: `apps/ade-api/src/ade_api/features/runs/service.py`
  - `prepare_run` creates the `runs` row and optional build context.
  - `stream_run` emits `run.queued`, proxies `build.*`/`console.line` via dispatcher when streaming the build, then streams engine telemetry, and emits `run.completed`.
  - `RunEventDispatcher` is injected via `_get_run_event_dispatcher` (settings singleton).
  - Engine execution is wrapped by `EngineSubprocessRunner` (tails engine-written `engine-logs/events.ndjson`).
  - Final payload built in `_run_completed_payload`; summary recomputed with `build_run_summary_from_paths`.

- **Run endpoints**: `apps/ade-api/src/ade_api/features/runs/router.py`
  - `POST /configurations/{configuration_id}/runs` (stream flag toggles SSE vs background).
  - `GET /runs/{run_id}/events` (JSON page, NDJSON download, or SSE with replay + live).
  - `GET /runs/{run_id}` (metadata) and `GET /runs/{run_id}/summary` (RunSummaryV1).
  - SSE formatter: `_sse_event_bytes` emits `event: ade.event` and `id: <sequence>`.

- **Build orchestration**: `apps/ade-api/src/ade_api/features/builds/service.py`
  - `stream_build` yields `build.*` and `console.line scope:"build"` from `VirtualEnvironmentBuilder`.
  - Build-only streams are returned directly (no dispatcher → no `event_id`/`sequence`).
  - Reuse path emits `build.completed` with `status:"active"` and `env.reason:"reuse_ok"`.

- **Build endpoints**: `apps/ade-api/src/ade_api/features/builds/router.py`
  - `POST /workspaces/{workspace_id}/configurations/{configuration_id}/builds` with optional `stream=true` for SSE.
  - Background builds use `_execute_build_background`.

- **Summary builder**: `apps/ade-api/src/ade_api/features/runs/summary_builder.py`
  - `build_run_summary_from_paths` reads NDJSON + manifest to produce `RunSummaryV1`.
  - Tracks `run.started`, `run.completed`, `run.error`, `run.table.summary`, `run.validation.summary`.

---

## 2. Streaming flow (run)

1. `create_run_endpoint` → `RunsService.prepare_run` → `RunEventDispatcher.emit("run.queued", ...)`.
2. When `stream=true`:
   - If `build_context` exists, `BuildsService.stream_build` events are re-enveloped by dispatcher (`source` preserved) and sent to SSE.
   - Engine is invoked via `EngineSubprocessRunner.stream()`, which tails `engine-logs/events.ndjson`; each `AdeEvent` is forwarded through dispatcher (assigning `event_id`/`sequence` and persisting to `logs/events.ndjson`).
   - Completion (`RunExecutionResult`) triggers `_run_completed_payload` and final `run.completed` emission (API-origin).
3. SSE formatting is constant (`event: ade.event`); `id` header set when `sequence` present.

Background (non-streaming) path uses the same `stream_run` coroutine executed inside a FastAPI `BackgroundTasks` entry.

---

## 3. RunSummary + persistence

- `RunSummaryV1` is stored on the `runs.summary` column; recomputed from events if invalid/missing.
- `RunResource` maps summary details (`engine_version`, `env_reason`, failure info, output counts) and exposes links for events/logs/output/diagnostics.
- `RunLogsResponse` surfaces DB-backed logs; `logfile` endpoint serves the NDJSON stream persisted by dispatcher.

---

## 4. Deviations vs original plan

- Engine is the primary source of `run.started`; API emits `run.started` only for validate-only and safe-mode short-circuits.
- `run.phase.completed` / `build.phase.completed` payload classes exist but are not emitted by current code paths.
- Engine logs are read from its own `engine-logs/events.ndjson`; ade-api does **not** wrap raw stdout into `console.line`.
- Dedicated build streaming bypasses `RunEventDispatcher`, so `event_id`/`sequence` are absent on build-only SSE.
