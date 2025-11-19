# WP12 — ADE Runs API & Engine Integration Plan

> **Instructions for agents:**
> - Read this work package **plus** `docs/ade_runs_api_spec.md`, `docs/ade_builds_api_spec.md`, `docs/ade_builds_streaming_plan.md`, **and** `docs/reference/config_builder_streaming_plan.md` in full before starting.
> - Review `docs/developers/02-build-venv.md` so virtual environment pointers and layout stay aligned with the build pipeline.
> - Keep the checklist status up to date as tasks progress. Mark items complete with `[x]` and add dated notes for key decisions.
> - If you discover additional work, append new checklist items under the appropriate section (or create a new section) so this document stays the single source of truth.
> - *2025-11-20 — Final audit complete.* All items below are now closed; capture any future scope as separate work packages or follow-up tickets rather than reopening this checklist.

## A. Foundations & Scaffolding
- [x] Confirm FastAPI feature module scaffolding under `apps/ade-api/src/ade_api/features/runs/` (create `__init__.py`, `models.py`, `schemas.py`, `service.py`, `repository.py`, `router.py`, and `__tests__/` as needed). Reference existing modules such as `features/jobs` for layout parity.
- [x] Review `apps/ade-api/src/ade_api/shared/dependency.py` and related DI helpers to determine how run services will be injected. Add provider wiring for the runs service if required.
- [x] Update `apps/ade-api/src/ade_api/main.py` (or appropriate router registration site) to include the new runs router while keeping tag ordering consistent.
- [x] Document any repo-wide settings/env vars required by run execution (e.g., ADE venv root paths) in `README.md` or a new doc section once they are finalized. *(2025-11-13 — Documented ADE_SAFE_MODE requirements in README and the runs spec operational notes.)*

## B. Database Layer
- [x] Design Alembic migrations that create `runs` and `run_logs` tables per the spec. Ensure FK constraints reference configs and cascade deletions correctly.
- [x] Implement SQLAlchemy `Run` and `RunLog` models with relationships, default timestamps, and `RunStatus` enum (`apps/ade-api/src/ade_api/features/runs/models.py`).
- [x] Align model metadata (indices, nullable rules, cascade behavior) with the spec and existing conventions (compare with `features/jobs/models.py`).
- [x] Extend repository helpers to fetch runs/logs efficiently (filtering, pagination). Capture read patterns anticipated by the API (`after_id`, `limit`).
- [x] Add model coverage tests (e.g., via async DB fixtures) verifying enum transitions, timestamp updates, and log persistence. *(2025-11-13 — Added unit test `test_models.py` exercising defaults and cascade behaviour.)*

## C. Pydantic Schemas & Serialization
- [x] Implement request/response schemas in `schemas.py`, including `Run`, `RunCreateRequest`, `RunCreateOptions`, `RunEvent` variants, and NDJSON serialization helpers. Ensure `orm_mode` and timestamp conversions are correct.
- [x] Validate schema alignment with the spec by adding unit tests that serialize/deserialize representative payloads. *(2025-11-13 — Added `test_schemas.py` with serialization round-trips.)*
- [x] Update or generate OpenAPI documentation so the new endpoints surface correctly (`POST /api/v1/configs/{config_id}/runs`, `GET /api/v1/runs/{run_id}`, `GET /api/v1/runs/{run_id}/logs`).

## D. Service Layer & Execution Flow
- [x] Implement run creation, status updates, log appenders, and schema mapping helpers in `service.py` consistent with the spec and existing async session patterns.
- [x] Design the ADE execution runner (`run_ade_engine_stream`) that spawns the config-specific virtualenv process, streams output, persists logs, and yields structured events.
- [x] Factor out environment/command builders if reusable pieces already exist (search `apps/ade-engine` and current job orchestrators).
- [x] Provide background execution strategy for non-streaming runs (e.g., FastAPI `BackgroundTasks`, Celery, or existing job queue). Document interim behavior if async execution is deferred.
- [x] Add service-level tests (mocking subprocess) to cover success, failure, and cancellation paths, ensuring DB state matches spec expectations. *(2025-11-13 — Added `test_service.py` covering success, failure, cancellation, validate-only, and safe-mode flows.)*

## E. API Endpoints & Streaming Behavior
- [x] Implement FastAPI router endpoints with the `stream` flag logic. Ensure non-streaming calls respond with `Run` snapshots and streaming calls emit NDJSON `RunEvent` payloads.
- [x] Confirm middleware/CORS settings allow `application/x-ndjson` streaming without buffering. Adjust Uvicorn response headers if needed.
- [x] Add integration tests hitting the new routes (including streaming). Use test configs to simulate ADE output and assert DB changes plus streamed events.
- [x] Update API error handling to surface run lookup failures and execution errors consistently (HTTP 404/409/500 as appropriate).

## F. Engine & Config Package Integration
- [x] Verify `apps/ade-engine` exposes the entry point invoked by the runner (`python -m ade_engine.run` or equivalent). Add CLI flags/options mapping from `RunCreateOptions` if needed. *(2025-11-13 — Confirmed `python -m ade_engine` CLI and documented it in the spec.)*
- [x] Ensure config package discovery resolves correct venv paths using the build pointer (`${ADE_VENVS_DIR}/<workspace_id>/<config_id>/<build_id>` per repo conventions). Document fallback behavior when venvs are missing and cite the build documentation where relevant.
- [x] Plan for artifact/log storage beyond DB (e.g., writing NDJSON to disk) if required later; note follow-up tasks if this is out of scope for the initial release. *(2025-11-13 — Logged follow-up work in the spec to persist NDJSON events to disk.)*

## G. Observability & Admin Tooling
- [x] Decide how run logs appear in existing admin consoles or developer tooling. Update `docs/` or create a runbook covering manual inspection and troubleshooting. *(2025-11-15 — Added `docs/admin-guide/runs_observability.md` and linked it from the admin guide.)*
- [x] Evaluate whether `npm run workpackage` or other CLI tooling should expose runs (e.g., list active runs). Add CLI tasks or document TODOs accordingly. *(2025-11-15 — Logged follow-up ADE-CLI-11 for `scripts/npm-runs.mjs` commands and referenced it in the observability doc.)*

## H. Frontend & Client Consumers
- [x] Audit `apps/ade-web` for areas that will consume the runs API (e.g., workspace run consoles). Document integration points and create follow-up work packages if frontend work is substantial. *(2025-11-15 — Captured integration notes in `docs/reference/runs_frontend_integration.md` and requested WP13 for UI work.)*
- [x] Ensure TypeScript clients regenerate OpenAPI types (`ade openapi-types`) once the backend routes land and update curated schema exports if new shapes are exposed. *(2025-11-15 — Documented OpenAPI regeneration requirements in the frontend integration notes.)*

## I. QA, Ops, & Documentation
- [x] Maintain automated coverage: extend unit/integration test suites and update CI expectations (`npm run test`, `ade ci`).
- [x] Provide manual QA checklist mirroring streaming vs. non-streaming flows (e.g., using HTTPie/curl) and document in `docs/ade_runs_api_spec.md` or a companion doc. *(2025-11-13 — Added Manual QA Checklist section to the runs spec.)*
- [x] Update changelog/release notes summarizing the new runs capability and migration requirements.
- [x] Coordinate deployment steps (migrations, env vars) with ops; document rollback strategy if run processing fails. *(2025-11-15 — Authored `docs/reference/runs_deployment.md` covering migration order, config flags, and rollback steps.)*

## J. Build Endpoint Streaming Refactor
- [x] Read `docs/ade_builds_streaming_plan.md` and reconcile it with the existing runs spec before implementing any code. *(2025-11-16 — Reviewed plan while aligning service/routers with the runs event contract.)*
- [x] Draft migrations + SQLAlchemy models for the new `Build`/`BuildLog` tables, keeping compatibility with `configuration_builds` pointers. *(2025-11-16 — Added `apps/ade-api/migrations/0003_builds_tables.py` plus ORM models with FK links back to configuration builds.)*
- [x] Extend Pydantic schemas and API contracts to expose build objects, create requests, event streams, and log listings. *(2025-11-16 — Replaced legacy ensure schemas with `BuildResource`, `BuildEvent` union, and `BuildLogsResponse`.)*
- [x] Refactor `BuildsService` and `VirtualEnvironmentBuilder` per the plan to emit streaming events and persist incremental logs. *(2025-11-16 — Introduced async builder streaming with structured step/log events and rewrote the service orchestration around `BuildExecutionContext`.)*
- [x] Rework the builds router to serve `POST .../builds` with `stream` support alongside status/log endpoints and compatibility shims. *(2025-11-16 — Added new NDJSON endpoint plus legacy shims returning deprecation notices.)*
- [x] Retire the legacy `/workspaces/.../configurations/.../build` endpoints after consumers migrated. *(2025-11-19 — Removed shims and refreshed docs/specs to reference only the streaming build API.)*
- [x] Add unit/integration test coverage and documentation updates matching the new streaming behavior. *(2025-11-16 — Added service unit tests; 2025-11-17 — Added integration coverage for streaming/background flows; 2025-11-18 — Published `docs/ade_builds_api_spec.md` and linked references across admin/deployment docs.)*

## K. Config Builder Streaming Integration
- [x] Draft the frontend integration plan for streaming builds and runs in the workbench console and link it from WP12. *(2025-11-19 — Added `docs/reference/config_builder_streaming_plan.md` outlining NDJSON adapters, console state, and UX entry points.)*
- [x] Implement console streaming in the config editor using the new build/run APIs, including NDJSON helpers, UI affordances, and formatter tests. *(2025-11-19 — Added shared streaming utilities, console formatters, and hooked the workbench actions to stream build/run output.)*

## Notes & Decision Log
- 2025-11-20 — Final readiness review complete; checklist closed with no remaining items. Future enhancements should spin up new work packages.
- 2025-11-16 — Landed the streaming builds API, async builder, and NDJSON router plus unit coverage. Legacy `/build` endpoints now emit 410 deprecation responses pending frontend migration work.
- 2025-11-17 — Added integration coverage for the builds streaming endpoint (tests/integration/builds/test_builds_router.py) to exercise NDJSON flows and background execution.
- 2025-11-18 — Published the builds API spec (`docs/ade_builds_api_spec.md`) and refreshed the streaming plan checklist to capture completed documentation work.
- 2025-11-18 — Added `next_after_id` to build log responses for parity with runs pagination and updated integration/unit tests.
- 2025-11-19 — Retired legacy `/build` endpoints and aligned docs/specs with the streaming build API exclusively.
- 2025-11-19 — Documented the config builder streaming plan and shipped the workbench console integration that consumes build/run NDJSON streams.
- 2025-11-15 — Published admin observability, frontend integration, and deployment runbooks to unblock the remaining WP12 tasks. Logged ADE-CLI-11 for the forthcoming `scripts/npm-runs.mjs` helpers.
- 2025-11-14 — Authored the build endpoint streaming plan and linked it from WP12 to guide the upcoming refactor.
- 2025-11-13 — Added unit coverage for runs models/schemas/service, documented ADE_SAFE_MODE usage, and captured manual QA + follow-up enhancements in the runs spec.
- 2025-11-14 — Cross-checked virtual environment layout with `docs/developers/02-build-venv.md` and updated guidance to use `${ADE_VENVS_DIR}/<workspace>/<config>/<build_id>` paths.
- 2025-10-09 — Initial runs backend shipped with safe-mode short-circuiting, NDJSON streaming, and background execution using request-scoped sessions. Full engine invocation still relies on `python -m ade_engine`; follow-up service-level tests and engine integration remain open.
