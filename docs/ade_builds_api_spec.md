# ADE Builds API Specification

This document pairs with `docs/ade_runs_api_spec.md` and the build streaming refactor
plan (`docs/ade_builds_streaming_plan.md`). It captures the API contract, database
entities, and orchestration flow that now power streaming build execution. Agents
implementing client code or extending the backend must read all three documents
before starting.

---

## 1. Core concepts & naming

* **Build** – Persistent record for one execution of the configuration build pipeline
  (mirrors `Run`). Exposed as object type `"ade.build"`.
* **Build status** – `queued | building | active | failed | canceled` (`BuildStatus`
  enum in `apps/api/app/features/builds/models.py`).
* **Build logs** – Text chunks captured from subprocess output and stored in
  `build_logs`. Exposed via `GET /api/v1/builds/{build_id}/logs` and NDJSON
  `build.log` events.
* **Build events** – Streamed objects emitted when `stream: true` is requested. All
  carry `object: "ade.build.event"` and share the `build_id`, `created`, and `type`
  fields.

### Object identifiers

* Build IDs follow the `build_<ulid>` format and are the primary key in the new
  `builds` table.
* Builds record foreign keys to `workspaces`, `configurations`, and the legacy
  `configuration_builds` row (`configuration_build_id` + `build_ref`) so existing
  pointers remain valid.

---

## 2. Database models & migrations

Alembic migration `apps/api/migrations/versions/0003_builds_tables.py` installs the
following tables (see `apps/api/app/features/builds/models.py`):

### 2.1 `builds`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `String` | Primary key (`build_<ulid>`). |
| `workspace_id` | `String(26)` | FK → `workspaces.id` (cascade delete). |
| `config_id` | `String(26)` | Plain column, indexed for quick lookup. |
| `configuration_id` | `String(26)` | FK → `configurations.id` (cascade delete). |
| `configuration_build_id` | `String(26)` nullable | FK → `configuration_builds.id` (set null on delete) so new builds can reference the existing pointer row. |
| `build_ref` | `String(26)` nullable | Stores the legacy `configuration_builds.build_id` value for observability/migrations. |
| `status` | `Enum(api_build_status)` | `queued/building/active/failed/canceled`. |
| `exit_code` | `Integer` nullable | Final process exit code. |
| `created_at`, `started_at`, `finished_at` | `DateTime(timezone=True)` | Lifecycle timestamps. |
| `summary`, `error_message` | `Text` nullable | Short narrative/error text. |

### 2.2 `build_logs`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `Integer` | Autoincrement primary key. |
| `build_id` | `String` | FK → `builds.id`, cascade delete. |
| `created_at` | `DateTime(timezone=True)` | Defaults to `CURRENT_TIMESTAMP`. |
| `stream` | `String(20)` | `stdout` or `stderr` (future extension). |
| `message` | `Text` | Raw text payload. |

The migration also upgrades `configuration_builds` to use SQLAlchemy enums and
single-column FKs so legacy ensure flows remain compatible with the new API.

---

## 3. Pydantic schemas

Defined in `apps/api/app/features/builds/schemas.py` using the shared
`BaseSchema` utilities.

### 3.1 `BuildResource`

```jsonc
{
  "id": "build_01HZYJV6R1W5W8S71KZ64C5GZG",
  "object": "ade.build",
  "workspace_id": "wrk_01HZYJQ0S7GCKR9X8BEYQQ3W7P",
  "config_id": "cfg_01HZYJQ6CZV9Q8F41E6N1YJ6Q1",
  "configuration_id": "cfg_01HZYJQ6CZV9Q8F41E6N1YJ6Q1",
  "configuration_build_id": "cbld_01HZYJW10QQPE8B4W83B4N4RRM",
  "build_ref": "01HZYJW10QQPE8B4W83B4N4RRM",
  "status": "building",
  "created": 1731902400,
  "started": 1731902405,
  "finished": null,
  "exit_code": null,
  "summary": null,
  "error_message": null
}
```

### 3.2 Create request

```jsonc
{
  "stream": true,
  "options": {
    "force": false,
    "wait": false
  }
}
```

`force` mirrors the legacy ensure flag, `wait` controls whether we allow parallel
rebuilds or block until existing builds finish.

### 3.3 Events

* `build.created` – emitted immediately after the row is inserted. Includes `status`
  and `config_id`.
* `build.step` – high-level lifecycle markers. `step` is one of
  `create_venv`, `upgrade_pip`, `install_engine`, `install_config`, `verify_imports`,
  or `collect_metadata`. Optional `message` provides human-friendly context.
* `build.log` – line-by-line text captured from subprocess stdout/stderr.
* `build.completed` – terminal event carrying the final `status`, `exit_code`,
  optional `error_message`, and optional `summary`.

`BuildEvent` is a discriminated union keyed by `type` to support automatic
serialization/deserialization.

### 3.4 Log polling

`BuildLogsResponse` wraps a list of `BuildLogEntry` items for
`GET /api/v1/builds/{build_id}/logs`. Pagination is handled with the `after_id`
query parameter, and the response includes `next_after_id` to signal the cursor
for the next page when the configured limit (1000 rows) is reached.

---

## 4. Service layer orchestration

`apps/api/app/features/builds/service.py` coordinates build execution:

1. `BuildsService.create_build(...)` inserts a new `Build` row with status
   `queued` and returns the ORM instance.
2. `_build_to_schema` converts ORM models into `BuildResource` responses, mirroring
   `runs.service.run_to_schema`.
3. `run_build_stream(...)` orchestrates execution:
   * Emits `build.created` immediately.
   * Transitions status to `building`, updates `started_at`, and yields
     `build.step` events as the builder reports progress.
   * Persists stdout lines to `build_logs` while yielding `build.log` events.
   * On completion, updates `status`, `exit_code`, `finished_at`, optionally sets
     `summary`/`error_message`, and emits `build.completed`.
4. Background execution (when `stream: false`) uses FastAPI `BackgroundTasks` to
   call the same coroutine and discard streamed events; the database still receives
   logs/status transitions so polling works identically.
5. Safe mode short-circuits execution: when `ADE_SAFE_MODE=true`, the service
   immediately records a `failed` build with a descriptive error message rather than
   invoking subprocesses.

The builder implementation lives in `apps/api/app/features/builds/builder.py`.
`VirtualEnvironmentBuilder.build_stream(...)` emits structured steps/log lines for
Python/`pip` commands using `asyncio.create_subprocess_exec`, ensuring stdout is
consumed incrementally.

---

## 5. API endpoints

All routes live in `apps/api/app/features/builds/router.py` and are mounted under
`/api/v1`.

### 5.1 Create / ensure build

`POST /api/v1/workspaces/{workspace_id}/configs/{config_id}/builds`

* Body: `BuildCreateRequest` (see above).
* `stream=false` (default) – returns `200 OK` with a `BuildResource` snapshot. The
  build is executed via background task.
* `stream=true` – returns `200 OK` streaming `application/x-ndjson`. Each line is a
  JSON-encoded `BuildEvent`. Clients must read until `build.completed`.
* Errors:
  * `404` if workspace/config cannot be resolved.
  * `409` if policy (e.g., single active build when `wait=false`) prevents
    immediate execution.
  * `503` if dispatcher queues exceed configured capacity.

### 5.2 Status polling

`GET /api/v1/builds/{build_id}` → `BuildResource` representing the latest
snapshot. Returns `404` if the ID is unknown or the caller lacks access.

### 5.3 Log polling

`GET /api/v1/builds/{build_id}/logs?after_id=<int>` → `BuildLogsResponse`. When
`after_id` is omitted the oldest logs are returned first. Consumers should continue
paging until fewer than the configured limit (1000) entries are returned.

### 5.4 Legacy compatibility

* `PUT /workspaces/.../build` and `GET/DELETE /workspaces/.../build` now delegate to
  the refactored service. The router returns HTTP 410 with migration guidance so
  clients transition to the new NDJSON endpoints.

---

## 6. Streaming protocol

* Media type: `application/x-ndjson`.
* Each event is serialized with `json.dumps(event.dict()) + "\n"` and flushed as
  bytes. Clients should treat the stream as line-delimited JSON.
* The first event is always `build.created`; the final event is `build.completed`.
* Consumers should treat `build.step` as coarse progress and rely on `build.log`
  events for textual output.

---

## 7. Observability & manual QA

* Admins can tail builds via:
  * Streaming the POST response with `stream=true` (e.g., `curl -N ...`).
  * Polling `/builds/{id}` for status and `/builds/{id}/logs` for captured output.
* Deployment guidance covering migrations, environment variables, and safe-mode
  testing lives in `docs/reference/runs_deployment.md` (shared runs/builds doc).
* The admin runbook (`docs/admin-guide/runs_observability.md`) references builds
  alongside runs for troubleshooting.
* Manual QA steps (HTTPie examples, error handling checks) mirror the runs spec and
  should be updated in tandem when behavior changes.

---

## 8. Follow-up work

* Backfill historical `configuration_builds` entries into the new `builds` table so
  all legacy builds surface through the API (tracked in WP12 decision log).
* Evaluate storing structured command metadata (duration, exit code, environment) in
  a dedicated table for richer observability.
* Once the React app adopts the new endpoints, regenerate TypeScript clients via
  `npm run openapi-typescript` and update curated schema exports under
  `apps/web/src/schema/`.

