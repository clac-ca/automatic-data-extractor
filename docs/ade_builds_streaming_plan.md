# ADE Build Endpoint Streaming Refactor Plan

This plan extends the ADE Runs specification (`docs/ade_runs_api_spec.md`) to cover the configuration build lifecycle. Follow the checklist below to refactor the build ensure endpoint so that it mirrors the event-driven pattern used for runs and future jobs.

> **Status (2025-11-20):** Final review complete. Phase 1–4 implemented in `apps/api/app/features/builds/` with async builder streaming, NDJSON routes, unit + integration coverage, and operator docs. Legacy `/build` endpoints have been removed now that all clients speak the new contract. Capture additional scope as follow-up tickets.

## 1. Goals & Non-Goals

- ✅ Provide a streaming-friendly build orchestration API that surfaces progress in real time via NDJSON events.
- ✅ Preserve backwards compatibility for clients that rely on synchronous "ensure" semantics while introducing a modern `stream` option.
- ✅ Align naming, response envelopes, and error handling with the runs API so future UI/client code can share adapters.
- ✅ Capture build step output in a structured form (events + optional persisted logs) instead of only raising exceptions on failure.
- ❌ Rewriting configuration storage or content hashing (existing repositories remain authoritative).
- ❌ Changing workspace authorization scope semantics.

## 2. Legacy State Summary (for context)

- Prior to the streaming refactor, `PUT /workspaces/{workspace_id}/configurations/{config_id}/build` triggered a blocking `BuildsService.ensure_build` call. The service invoked `VirtualEnvironmentBuilder.build`, which performed all subprocess calls via `subprocess.run` inside a threadpool.
- There was no concept of incremental progress events. Errors surfaced only as HTTP 500 responses with a `build_failed` detail payload.
- Clients that wanted non-blocking behavior passed `{ "wait": false }` and polled, but they still had no insight into what the builder was doing.
- `VirtualEnvironmentBuilder.build` supported a `stream_output` flag, but it only disabled `capture_output`; stdout/stderr were sent to the API process logs, not to the caller, and the text was discarded afterwards.
- As of 2025-11-19, the legacy `/build` endpoints have been fully removed in favor of the new streaming-friendly API detailed below.

## 3. Target API Shape (mirrors Runs)

| Behavior | Request | Response |
| --- | --- | --- |
| Non-streaming (background) | `POST /api/v1/workspaces/{workspace_id}/configs/{config_id}/builds` with `{ "stream": false, "options": { "force": false, "wait": false } }` | JSON `Build` object snapshot (status `queued`/`building`/`active`/`failed`) |
| Streaming ensure | same route with `{ "stream": true, ... }` | `application/x-ndjson` event stream with `build.created`, `build.step`, `build.log`, `build.completed` events |
| Status polling | `GET /api/v1/builds/{build_id}` | JSON `Build` snapshot |
| Log fetch | `GET /api/v1/builds/{build_id}/logs?after_id=...` | Paginated log entries |

Design decisions:

1. Introduce a `Build` resource (id: `build_<ulid>`) decoupled from the `ConfigurationBuild` pointer table. Persist the new build records and logs alongside the existing `configuration_builds` rows to keep compatibility.
2. Allow `stream: false` requests to enqueue work onto a background task (similar to runs). The HTTP response returns immediately with the new `Build` snapshot.
3. `stream: true` executes inline and yields NDJSON `BuildEvent` lines following the same shape as `RunEvent`.
4. Extend the builder so every subprocess step emits a `build.step` event with machine-readable step identifiers (`"create_venv"`, `"upgrade_pip"`, `"install_engine"`, `"install_config"`, `"verify_imports"`, `"collect_metadata"`). Line-by-line stdout becomes `build.log` events.
5. Persist log chunks to a `build_logs` table to support `/logs` pagination and cross-session viewing.
6. Maintain compatibility with existing `GET/DELETE /build` endpoints by keeping a thin adapter that delegates to the new service (optional follow-up to deprecate `PUT /build`).

## 4. Implementation Roadmap

### Phase 1 — Data & Schemas

- [x] Design new SQLAlchemy models (`Build`, `BuildLog`) plus Alembic migration. Model fields should parallel the runs schema (status enum, timestamps, exit codes, summary/error, FK to config/workspace). *(2025-11-16 — Added models/migration in `apps/api/app/features/builds/models.py` + `migrations/0003_builds_tables.py` mirroring the runs schema conventions.)*
- [x] Add Pydantic schemas: `Build`, `BuildCreateRequest`, `BuildCreateOptions`, `BuildEvent` union, `BuildLogEntry`, `BuildLogsResponse`. *(2025-11-16 — Implemented in `features/builds/schemas.py` with `BaseSchema` alignment and discriminator-based events.)*
- [x] Decide whether to soft-link existing `configuration_builds` rows (e.g., storing `active_configuration_build_id` on the new `Build`). Document the mapping strategy. *(Decision: store optional `configuration_build_id` FK plus `build_ref` (the legacy `configuration_builds.build_id`) so historical pointers remain accessible without data migration.)*

### Phase 2 — Service Layer

- [x] Refactor `BuildsService` into smaller collaborators: creation, status updates, log appenders, background dispatch, streaming orchestrator. *(2025-11-16 — Introduced `BuildExecutionContext` and repository helpers to isolate creation/status/log responsibilities.)*
- [x] Replace the blocking `VirtualEnvironmentBuilder.build` with an async generator (`build_venv_stream`) that:
  * Uses `asyncio.create_subprocess_exec` for each pip/python command.
  * Yields structured step events and log lines.
  * Records progress in the database via new repositories.
  *(2025-11-16 — `VirtualEnvironmentBuilder.build_stream` now streams commands, and `BuildsService.run_build_stream` persists events/logs.)*
- [x] Ensure safe-mode, timeout, and TTL semantics remain intact. Document any changes to error propagation. *(2025-11-17 — Safe mode short-circuits within `BuildsService` and error propagation documented in the admin/deployment notes.)*
- [x] Expose helper(s) to convert ORM rows to API schemas (`build_to_schema`), mirroring `run_to_schema`. *(2025-11-16 — Added `_build_to_schema` mapper to the service module.)*

### Phase 3 — API Endpoints

- [x] Introduce a new router under `/api/v1/workspaces/{workspace_id}/configs/{config_id}/builds` with `POST` (create/ensure) supporting `stream`. *(2025-11-16 — Implemented NDJSON streaming endpoint in `features/builds/router.py`.)*
- [x] Provide `GET /api/v1/builds/{build_id}` and `GET /api/v1/builds/{build_id}/logs` for status/log polling. *(2025-11-16 — Added read/log routes aligned with runs API semantics.)*
- [x] Retire the legacy `/workspaces/.../configurations/.../build` routes once all clients migrate. *(2025-11-19 — Removed transitional shims; API surface now consists solely of the streaming build endpoints.)*
- [x] Update dependency wiring (`get_builds_service`) to construct the refactored service. *(2025-11-16 — Dependency module now provides the refactored service + builder collaborators.)*

### Phase 4 — Observability & Clients

- [x] Add integration tests covering streaming vs. background flows (mocking subprocesses where necessary) similar to `apps/api/tests/integration/runs/test_runs_router.py`. *(2025-11-17 — Added `tests/integration/builds/test_builds_router.py` with stubbed builder flows.)*
- [x] Provide unit tests for the builder stream, service transitions, and log persistence. *(2025-11-16 — Expanded `tests/unit/features/builds/test_service.py` to cover success/failure/cancel/safe-mode scenarios.)*
- [x] Update documentation (README, changelog, admin guides) with the new endpoints, event examples, and migration notes. *(2025-11-18 — Authored `docs/ade_builds_api_spec.md`, expanded changelog/admin references, and linked migration steps from deployment notes.)*
- [x] Coordinate OpenAPI updates and TypeScript regeneration once backend routes stabilize. *(2025-11-18 — Documented regeneration requirements alongside the new spec; tooling update pending frontend adoption.)*

## 5. Open Questions / Follow-ups

- How do we map historical `configuration_builds` data into the new tables? (Option: create `Build` entries on demand when legacy data is accessed.)
- Should we enforce mutual exclusion between build and run pipelines for the same config? Document policy decisions.
- Explore storing full command metadata (duration, exit code, env) for observability.

## 6. References

- Runs spec: `docs/ade_runs_api_spec.md`
- Virtual environment guide: `docs/developers/02-build-venv.md`
- Existing build orchestration: `apps/api/app/features/builds/service.py`, `builder.py`

---

Keep this plan synchronized with the WP12 work package. If new discoveries emerge (e.g., additional tables, CLI changes), append them to both this document and WP12 with context and decision log entries.
