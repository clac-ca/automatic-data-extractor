# Event Types - Current vs New (Implemented)

This file reflects the **shipped code** for the ADE event envelope and payloads. Envelope and payload models live in `apps/ade-engine/src/ade_engine/schemas/telemetry.py` and are imported by ade-api.

---

## 1. Canonical envelope (`AdeEvent`)

Envelope fields:

- `type`: string
- `event_id`: optional string (assigned by ade-api `RunEventDispatcher`)
- `created_at`: `datetime`
- `sequence`: optional int (assigned by `RunEventDispatcher`; monotonic per `run_id`)
- `source`: optional string (`api` | `engine` | others)
- `workspace_id`, `configuration_id`, `run_id`, `build_id`: optional strings
- `payload`: `AdeEventPayload | dict | None`

Event IDs and sequences are **only** added when ade-api emits through `RunEventDispatcher` (`apps/ade-api/src/ade_api/features/runs/event_dispatcher.py`). The dispatcher persists events to `.../runs/{run_id}/logs/events.ndjson` and replays them with `RunEventLogReader`.

---

## 2. Event types and payloads (as emitted today)

### Build lifecycle (`BuildsService.stream_build`)

- `build.created` — payload: `status: "queued"`, `reason` (`"force_rebuild"` or `"dirty_or_missing"`), `should_build` (bool), `engine_spec`, `engine_version_hint`, `python_bin`.
- `build.started` — payload: `status: "building"`, `reason`.
- `build.phase.started` — payload: `phase` in `{create_venv, upgrade_pip, install_engine, install_config, verify_imports, collect_metadata}`, optional `message`.  
  **Note:** there is **no** `build.phase.completed` emitted in current code.
- `console.line` (build scope) — payload: `scope:"build"`, `stream:"stdout"|"stderr"`, `level` (`"warning"` on stderr, `"info"` otherwise), `message`.
- `build.completed` — payload: `status` (`"active"`, `"failed"`, `"canceled"`, `"queued"`, `"building"`), `exit_code`, `summary`, `duration_ms`, `error` (with `message`), `env` (`reason`, and on reuse `should_build:false`, `force`, `reason:"reuse_ok"`).

### Run lifecycle (`RunsService.stream_run` + engine telemetry)

- `run.queued` (API) — payload: `status:"queued"`, `mode` (`"execute"` | `"validate"`), `options` (raw `RunCreateOptions`), optional `queued_by` (unused today).
- `run.started`
  - Engine-origin (normal runs): payload includes `status:"in_progress"`, `engine_version`.
  - API-origin (validate-only or safe-mode short-circuits): payload includes `status:"in_progress"`, `mode`, optional `env`.
- `run.phase.started` (engine) — payload: `phase` (`extracting`, `mapping`, `normalizing`, `writing_output`, etc.), optional `message`.  
  **Note:** engine does **not** emit `run.phase.completed` today.
- `run.table.summary` (engine) — payload includes `table_id`, `source_file`, `source_sheet`, `table_index`, `row_count`, `column_count`, `mapped_fields`, `mapping.mapped_columns`/`mapping.unmapped_columns`, `unmapped_column_count`, `validation` (`total`, `by_severity`, `by_code`, `by_field`), `details` (`header_row`, `first_data_row`, `last_data_row`).
- `run.validation.summary` (engine) — payload: `issues_total`, `issues_by_severity`, `issues_by_code`, `issues_by_field`, `max_severity`.
- `run.validation.issue` (engine, optional/high-volume) — payload: `severity`, `code`, `field`, `row`, `message`.
- `run.error` (engine when `error_to_run_error` triggers) — payload: `stage`, `code`, `message`, optional `phase`, `details`.
- `run.completed` (API) — built via `RunsService._run_completed_payload` with:
  - `status`: `succeeded` | `failed` | `canceled`
  - `failure`: `{stage, code, message}` or `null`
  - `execution`: `{exit_code, started_at, completed_at, duration_ms}`
  - `artifacts`: `{output_paths, events_path}`
  - `summary`: serialized `RunSummaryV1` or `null`

### Logging (`console.line`)

Payload class: `ConsoleLinePayload(scope, stream, level="info", message, phase?, logger?, engine_timestamp?)`.

- Build logs: emitted from `BuilderLogEvent` with `scope:"build"`.
- Run logs: emitted from engine `PipelineLogger.note(...)` with `scope:"run"`; ade-api does **not** wrap raw stdout from the engine process.

---

## 3. Migration table (v1 → new)

| v1 Event                   | New Event / Status                        | Notes                                                                                |
| -------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------ |
| `build.created`            | **Kept**, payload refined                 | reason values are `force_rebuild`/`dirty_or_missing`.                                |
| `build.started`            | **Kept**, payload refined                 | status is always `building`.                                                         |
| `build.phase.started`      | **Kept**                                  | Emitted for each builder step.                                                       |
| `build.console`            | **Removed** → `console.line`              | Use `console.line` with `scope:"build"`.                                             |
| `build.completed`          | **Kept**, payload refined                 | Reuse path reports `status:"active"` + `env.reason:"reuse_ok"`.                      |
| `run.queued` (api)         | **Kept**, payload refined                 | Includes raw `RunCreateOptions`.                                                     |
| `run.started` (api)        | **Partial**                               | API only emits for validate-only/safe-mode runs.                                     |
| `run.started` (engine)     | **Kept**                                  | Engine emits `run.started` with `status`/`engine_version`.                           |
| `run.console` (api/engine) | **Removed** → `console.line`              | Unified log event.                                                                   |
| `run.completed` (api)      | **Replaced** by canonical `run.completed` | API is sole emitter of final completion.                                             |
| `run.completed` (engine)   | **Kept (internal)**                       | Engine emits its own; API rewrites/extends when finalizing.                          |
| `run.phase.started`        | **Kept**                                  | Only `run.phase.started` is emitted today.                                           |
| `run.phase.completed`      | **Not emitted**                           | Payload class exists but is unused.                                                  |
| `run.table.summary`        | **Kept**, payload refined                 | Includes mapping + validation aggregates.                                            |
| `run.validation.issue`     | **Kept (optional)**                       | High-volume debug event.                                                             |
| `run.validation.summary`   | **Kept**, payload clarified               | Matches engine aggregation helper.                                                   |
| Envelope `details`/`error` | **Removed**                               | Use payload fields and `run.error`/`run.completed.failure`.                          |
| `console.line`             | **New**                                   | Unified logging for build + run.                                                     |
| `build.phase.completed`    | **Not emitted**                           | Payload class exists but unused.                                                     |
| `run.error`                | **New**                                   | Engine-origin structured errors.                                                     |

Anything under "Removed" should not appear in ade-api/ade-engine/ade-web going forward.
