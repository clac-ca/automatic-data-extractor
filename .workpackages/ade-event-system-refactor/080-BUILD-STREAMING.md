# Build Streaming (Current)

How build-only streaming and build integration in run streams are implemented.

---

## 1. Dedicated build endpoint

- Route: `POST /workspaces/{workspace_id}/configurations/{configuration_id}/builds`
- Handler: `apps/ade-api/src/ade_api/features/builds/router.py::create_build_endpoint`
- Behavior:
  - `stream=false` → returns `BuildResource`; background execution via `_execute_build_background`.
  - `stream=true` → streams SSE (`event: ade.event`) from `BuildsService.stream_build`.
    - Events are `build.created`, `build.started`, `build.phase.started`, `console.line scope:"build"`, `build.completed`.
    - No `event_id`/`sequence` (bypasses `RunEventDispatcher`); no persisted NDJSON for build-only streams.

## 2. Build stream contents (`BuildsService.stream_build`)

- `build.created`: reason is `"force_rebuild"` or `"dirty_or_missing"`; includes `should_build`, `engine_spec`, `engine_version_hint`, `python_bin`.
- `build.started`: status `"building"`, same `reason`.
- `build.phase.started`: phases from `BuilderStep` (`create_venv`, `upgrade_pip`, `install_engine`, `install_config`, `verify_imports`, `collect_metadata`); message mirrors builder step text. **No `build.phase.completed` emitted.**
- `console.line`: emitted for pip/venv subprocess output with `scope:"build"`, `stream` (`stdout`/`stderr`), `level` (`warning` on stderr else `info`), `message`.
- `build.completed`: status reflects `BuildStatus` (`active`, `failed`, `canceled`, etc.); reuse path sets `status:"active"` with `env.reason:"reuse_ok"`, `env.should_build:false`, `env.force`.

## 3. Build integration in run streaming

- When `create_run_endpoint` is invoked with `stream=true`, `RunsService.stream_run` may create a `build_context`.
- `BuildsService.stream_build` events are re-enveloped via `RunEventDispatcher.emit` with `run_id`/`build_id`, gaining `event_id`/`sequence` and being persisted to `runs/{run_id}/logs/events.ndjson`.
- After a successful build, ade-api emits a banner `console.line` (`scope:"run"`, `message:"Configuration build completed; starting ADE run."`) before engine execution.
- Non-streaming run creation (`stream=false`) relies on `_ensure_config_env_ready` and does **not** stream build events.

## 4. Deviations from the original target

- No `build.phase.completed` events are emitted.
- Build-only SSE streams are transient (not persisted/replayable); run-integrated builds are persisted via `RunEventDispatcher`.
