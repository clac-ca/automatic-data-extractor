# Frontend Streaming (Implemented)

How ade-web consumes the unified run stream after the refactor.

---

## 1. Entry points

- **API helpers**: `apps/ade-web/src/shared/runs/api.ts`
  - `streamRun(configId, options, signal)` → creates run via `POST /configurations/{config_id}/runs` (`stream:false`) then attaches SSE.
  - `streamRunEvents(url, signal)` → wraps `EventSource`, listens for `ade.event` (and default `message`), parses JSON into `AdeEvent`, closes when `type === "run.completed"`.
  - Events URL built as `/api/v1/runs/{run_id}/events?stream=true&after_sequence=0`.

- **Types**: `apps/ade-web/src/shared/runs/types.ts`
  - `AdeEvent` shape mirrors backend envelope; `eventTimestamp` helper normalizes timestamps.

---

## 2. Shared state and reducer

- **State**: `RunStreamState` in `apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/state/runStream.ts`:
  - `runId`, `status` (`idle` \| `queued` \| `building` \| `running` \| `succeeded` \| `failed` \| `canceled`)
  - `buildPhases`/`runPhases` (phase → `{status, durationMs?, message?}`)
  - `consoleLines` (clamped to `maxConsoleLines`)
  - `tableSummaries`, `validationSummary`, `completedPayload`, `lastSequence`

- **Reducer**: `runStreamReducer` with actions `RESET`, `CLEAR_CONSOLE`, `APPEND_LINE`, `EVENT`.
  - `applyEventToState` handles `build.*`, `run.*`, and `console.line` (scope-based) to update status, phases, summaries, and console lines.
  - Status resolution: `run.queued` → queued, `build.started` → building, `run.started` → running, `run.error` → failed (if not already), `run.completed` → terminal status.
  - Console rendering uses `describeBuildEvent`/`describeRunEvent` (`.../utils/console.ts`) to convert events into human-readable lines with timestamps from `eventTimestamp`.

---

## 3. SSE usage

- `EventSource` is instantiated with `withCredentials: true`, listening on both `ade.event` and default `message`.
- On error: closes the stream and surfaces an error unless the abort signal fired.
- On `run.completed`: closes the stream after delivering the event.
- Reconnect logic is left to callers; `after_sequence=0` is used for initial replay.

---

## 4. Rendering pattern (Config Builder workbench)

- Workbench components consume `RunStreamState` (see reducer above) to drive:
  - Console output (build + run lines mixed, origin-tagged)
  - Build/run phase progress
  - Validation summary and table cards
  - Final run completion status/summary
- Console helper functions handle `console.line` scope/level/stream mapping and format durations (`duration_ms`) when present.

---

## 5. Notes vs original plan

- Frontend always uses the **attach-then-stream** approach (`stream:false` on creation, SSE attach immediately after) because `EventSource` only supports GET.
- Streams close client-side on `run.completed` rather than waiting for server disconnect.
- Reducer tolerates events without `sequence` (build-only SSE) by keeping `lastSequence` unchanged.
