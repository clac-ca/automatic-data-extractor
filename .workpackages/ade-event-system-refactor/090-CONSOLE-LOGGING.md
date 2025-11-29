# Console Logging and Subprocess Streaming (Current)

`console.line` is the single logging event across build + run. This doc reflects the shipped implementation.

---

## 1. `console.line` payload

Payload class: `ConsoleLinePayload(scope, stream, level="info", message, phase?, logger?, engine_timestamp?)` in `apps/ade-engine/src/ade_engine/schemas/telemetry.py`.

- `scope`: `"build"` or `"run"`
- `stream`: `"stdout"` or `"stderr"`
- `level`: default `"info"`; build logs map stderr → `"warning"`
- `message`: required string
- Optional: `phase`, `logger`, `engine_timestamp`

---

## 2. Sources of console events

- **Builds** (`BuildsService.stream_build`)
  - `VirtualEnvironmentBuilder` emits `BuilderLogEvent`; service converts to `console.line` with `scope:"build"`, `stream`, `level` (`warning` on stderr), `message`.

- **Engine** (`PipelineLogger.note`)
  - Engine writes structured `console.line` events directly to `engine-logs/events.ndjson` with `scope:"run"`.
  - Additional structured events (`run.*`, `run.table.summary`, etc.) are written to the same file.

---

## 3. How ade-api forwards logs

- `EngineSubprocessRunner` tails `engine-logs/events.ndjson`; any parsed `AdeEvent` (including `console.line`) is forwarded through `RunEventDispatcher.emit`, which stamps `event_id`/`sequence` and persists to `logs/events.ndjson`.
- Raw stdout from the engine process is **not** wrapped into `console.line`; only structured events written by the engine telemetry sink are streamed.
- Build console lines are emitted directly by ade-api (not the engine) and go through the dispatcher when part of a streamed run.

---

## 4. Frontend usage

- UI filters `console.line` and uses `payload.scope` to distinguish build vs run lines (`apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/console.ts`).
- Lines are rendered with levels mapped to styling; `runStreamReducer` clamps console history to `maxConsoleLines`.
