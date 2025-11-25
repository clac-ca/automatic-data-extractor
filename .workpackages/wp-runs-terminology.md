# Work Package: Replace "jobs" with "runs" across ADE

## Work Package Checklist

- [x] Finalize target terminology and scope (runs-only, zero “job” remnants) across backend, frontend, docs, settings
- [x] Plan DB/schema migration: extend runs if needed; drop jobs tables/enums/migrations
- [x] Plan storage/env rename to ADE_RUNS_DIR and path layout `data/runs/<run_id>/...`
- [x] Plan API/router and service removals (delete jobs feature; runs endpoints cover all)
- [x] Plan frontend migration (remove jobs module/UI; runs-only); regenerate OpenAPI types
- [x] Plan docs sweep to remove “job(s)” and align run terminology and examples

---

# Runs-Only Terminology Migration

## 1. Objective

**Goal:**
Move the codebase, APIs, storage, and docs to a single execution concept: **run**. Eliminate the "job" terminology and infrastructure.

You will:

* Define the target naming, data model, and storage layout for runs.
* Plan schema/API removals for jobs and consolidate functionality under runs.
* Outline frontend/docs updates and env var/storage changes.

The result should:

* Have **no user-facing or code-level “job” terminology, routes, settings, or storage**; runs-only everywhere.
* Use runs for storage, IDs, settings, and telemetry with a clean migration path (no backward compatibility).

## 1.1 Terminology and scope (finalized)

**Canonical term:** `run` / `run_id` / `runs` across all layers; never `job`.

**Back end:**

* Storage root is `ADE_RUNS_DIR`, defaulting to `./data/runs`; all path helpers and settings use `runs_dir` naming.
* Only runs data model/tables remain (`runs`, `run_logs`), with any legacy job metadata migrated or dropped; no jobs enums.
* API surface is `/runs` + config/workspace-scoped runs routes; delete `/jobs` routers and `JobsService` entirely.

**Engine/CLI:**

* Runtime paths and telemetry refer to runs (e.g., `run_dir`, `run_logs`); staging helpers cannot mention jobs.

**Frontend:**

* Shared client/hooks live under `shared/runs`; workspace history/navigation uses Runs naming and routes.
* UI copy, filenames, and query keys are run-only; no jobs module or imports.

**Docs/examples:**

* All prose and examples reference runs, `ADE_RUNS_DIR`, and `data/runs/<run_id>/...` paths; remove or rewrite any “job” wording.

---

## 2. Context (What you are starting from)

The repo currently has parallel concepts:

* Engine/CLI and new API: “runs” (tables `runs`/`run_logs`, routers under `/runs`, storage under `data/jobs/<run_id>` by convention).
* Legacy layer: “jobs” (table `jobs`, router `/workspaces/{id}/jobs`, staging logic in `JobsService`, frontend jobs list).
* Settings/env: `ADE_JOBS_DIR` drives storage paths; docs mix “job”/“run”; some docs are empty or archived.
* Frontend: Workspace “Jobs” screen hits jobs endpoints; runs shared module exists for new flows; navigation and docs call out jobs.
* Migrations: jobs FK migration exists (`0006_jobs_config_fk`); runs have their own migrations (`0002`, `0004`, `0005`).

Pain points:

* Duplicate persistence, staging, and status mapping between jobs and runs.
* User-facing inconsistency and docs drift.
* Storage/env naming still “jobs”.

Constraints:

* No backward compatibility required. History may be migrated to runs or discarded; do not keep jobs endpoints/aliases/settings.

---

## 3. Target architecture / structure (ideal)

Runs are the single execution primitive:

* Database: only `runs` and `run_logs` tables (extended with any required metadata such as submitter/config version if needed), no `jobs` table or enums.
* API: only runs endpoints (config-scoped create/stream, global get/logs/artifact/outputs, optional workspace-scoped listing). No jobs router.
* Services: `RunsService` owns staging, execution, artifacts, outputs; no `JobsService`.
* Storage: `ADE_RUNS_DIR` is the sole setting, directories keyed by `run_id`: `data/runs/<run_id>/{input,output,logs}`.
* Frontend: runs-only shared API/types; Workspace history page shows runs; no jobs module.
* Docs: consistent “run” terminology and updated paths/CLI references; no “job” wording remains.

```text
apps/ade-api/
  src/ade_api/features/runs/        # sole execution feature (schemas, service, router, supervisor, runner)
  migrations/versions/              # migrations to drop jobs, extend runs if needed
apps/ade-web/
  src/shared/runs/                  # API/types/hooks for runs
  src/screens/Workspace/sections/Runs/  # history UI
data/
  runs/<run_id>/input|output|logs/
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* Clarity: one term (“run”) across code, API, storage, UI, docs.
* Maintainability: remove duplicate logic/tables/routes; simplify services.
* Safety: provide a clear migration path for schema and storage; avoid ambiguous state.

### 4.2 Key components / modules

* Runs API (`apps/ade-api/src/ade_api/features/runs/*`) — execution lifecycle, staging, telemetry.
* Settings/storage (`Settings`, `ADE_RUNS_DIR`) — configure run storage root and path helpers.
* Frontend runs client/UI (`apps/ade-web/src/shared/runs/*`, Workspace Runs screen) — user-facing history and artifacts/logs.

### 4.3 Key flows / pipelines

* Run creation/streaming: `POST /configs/{config_id}/runs` → `RunsService.prepare_run`/`stream_run` → storage under `runs/<run_id>/`.
* Run history: workspace-scoped list/filter via runs endpoints; download artifacts/logs/outputs via runs routes.

### 4.4 Open questions / decisions

* Which job-only fields to carry into runs before dropping jobs? Candidates: `attempt`, `retry_of_job_id` (rename to run), `input_documents` array, `submitted_by_user_id`, `config_version_id`, artifact/log/output URIs, `trace_id`. Any not carried will be dropped with jobs.
* Workspace-scoped listing: add `/workspaces/{workspace_id}/runs` with filters (`status`, `input_document_id`, pagination) to replace `/jobs` for the UI (no alias/compat).

---

## 5. DB/schema migration plan (runs-only)

### 5.0 Execution checklist

- [x] Confirm final list of job-only fields to migrate or drop.
- [x] Add migration to extend `runs`/`run_logs` with retained fields (attempt, retry, submitter, config version, trace_id, input docs, artifact/log/output URIs).
- [x] Add migration to drop `jobs` table/enums and remove legacy Alembic path (`0006_jobs_config_fk`, etc.).
- [x] Remove jobs SQLAlchemy models/schemas/services and wire runs replacements.
- [x] Update settings/env references to use `runs_dir` only.
- [x] Update/run backend tests to assert runs-only schema and storage paths.

### 5.1 Approach and sequencing

1. **Pre-work:** audit any fields only present on `jobs` that we still need (likely: `attempt`, `retry_of_job_id` → `retry_of_run_id`, `input_documents` array, `submitted_by_user_id`, `config_version_id`, `trace_id`, artifact/log/output URIs). Freeze the final set before writing migrations. *Status:* ☑
2. **Migration A — extend runs:** add columns to `runs` and `run_logs` as needed (nullable defaults; backfill from `jobs` if we choose to migrate history). Add indexes/constraints that existed on jobs (e.g., `config_id + status`, `workspace_id + created_at` for history queries). *Status:* ☑
3. **Migration B — drop jobs:** delete `jobs` table, enums, FKs, and the `0006_jobs_config_fk` migration path. Remove SQLAlchemy models and Alembic references under `apps/ade-api/src/ade_api/features/jobs/` and `apps/ade-api/migrations/versions/`. *Status:* ☑
4. **Migration C — cleanup deps:** remove dependency wiring (`get_jobs_service`, router registration) and any dead settings/validation tied to `jobs_dir`. Ensure settings only expose `runs_dir`/`ADE_RUNS_DIR`. *Status:* ☑
5. **Data migration strategy:** if retaining history, write a one-time Alembic script to copy rows from `jobs` to `runs`, mapping renamed columns and converting job IDs to run IDs. If discarding, explicitly drop without copy to avoid partial data. *Status:* ☑ (dropping legacy jobs without backfill; runs-only going forward)
6. **Ordering:** run Migration A then B in the same release; block deploys that still reference jobs code/routers. Coordinate with OpenAPI regeneration after backend jobs routes are removed. *Status:* ☑

### 5.2 Code/tests to touch

* **Alembic migrations:** create new versions for extending runs and dropping jobs; delete legacy jobs migration files once superseded.
* **Models/schemas:** remove `apps/ade-api/src/ade_api/features/jobs/*`; ensure `runs` models include migrated columns and enums; update Pydantic schemas to expose new run fields.
* **Tests:** drop jobs tests; update runs integration tests to assert new columns and storage paths (`data/runs/<run_id>/...`).
* **Settings/paths:** switch remaining `jobs_dir` references in settings, lifecycle helpers, and error messages to `runs_dir`/`ADE_RUNS_DIR`; confirm migrations/tests use the new naming.

### 5.3 Risks and mitigations

* **Risk:** orphaned data if runs backfill fails. *Mitigation:* migration script should be idempotent with clear logging; run in maintenance window.
* **Risk:** API consumers still calling `/jobs`. *Mitigation:* remove router entirely and regenerate OpenAPI/types to force compile-time failures.
* **Risk:** stale storage references (`data/jobs`). *Mitigation:* provide storage rename step in settings and adjust path helpers/tests before deploying migrations.

### 5.4 Final field decisions (runs baseline)

* **Carry forward into `runs`:**
  * Execution metadata: `attempt` (int), `retry_of_run_id` (string ULID), `trace_id` (string), `submitted_by_user_id` (nullable FK), `config_version_id` (string ULID) alongside existing `config_id`.
  * Input context: `input_documents` JSON array (document id + filename tuples) preserved for workspace/document history, plus optional `input_sheet_name`/`input_sheet_names` already present.
  * Storage pointers: `artifact_uri`, `output_uri`, `logs_uri` as nullable text fields to capture relative run paths (replace jobs URI columns 1:1) and map to `RunResource.artifact_path/events_path/output_paths` when exposed.
  * Timing: keep `queued_at` semantics by reusing `runs.created_at`; map `started_at`/`completed_at`/`cancelled_at` to `started_at`/`finished_at`/`canceled_at` (new) columns for parity.

* **Drop without replacement:**
  * `input_hash` (unused dedupe hint), `last_heartbeat` (unused liveness probe), and `run_request_uri` (derivable from run id) will be omitted from the runs schema and associated docs/tests.

## 6. Storage/env rename plan (ADE_RUNS_DIR and `data/runs/<run_id>`)

### 6.0 Execution checklist

- [x] Add `ADE_RUNS_DIR`/`runs_dir` setting and remove `ADE_JOBS_DIR` usage/validation.
- [x] Rename storage helpers and defaults from `data/jobs/<id>` to `data/runs/<run_id>`.
- [x] Update engine/CLI staging/output helpers to use runs naming and telemetry.
- [x] Update backend runs service paths and settings validation to runs-only.
- [x] Update tests/fixtures to assert `runs` storage layout and env var handling.
- [x] Sweep docs/README/AGENTS for `ADE_RUNS_DIR` and storage rename instructions.

### 6.1 Objectives

* Replace `ADE_JOBS_DIR`/`jobs_dir` with `ADE_RUNS_DIR`/`runs_dir` across settings, CLI, engine, backend, and docs.
* Standardize runtime paths to `data/runs/<run_id>/{input,output,logs}`; no dual `jobs`/`runs` support.
* Keep migrations and settings validation aligned so deploys fail fast if `ADE_RUNS_DIR` is misconfigured.

### 6.2 Plan and sequencing

1. **Settings swap:**
   * Add `runs_dir` setting with env var `ADE_RUNS_DIR`; remove/ignore `ADE_JOBS_DIR` with a clear validation error if present. *Status:* ☑
   * Update path helpers in `ade_api/shared/core/lifecycles.py` (and any run service helpers) to resolve from `runs_dir`. *Status:* ☑
2. **Storage layout update:**
   * Rename helper functions and constants from `job*` to `run*` and change default path segments from `data/jobs/<id>` to `data/runs/<run_id>`. *Status:* ☑
   * Update error messages, logs, and docstrings to “runs directory” language. *Status:* ☑
3. **Engine/CLI alignment:**
   * Update CLI staging/output helpers to honor `ADE_RUNS_DIR` and `run_dir` naming; remove `job_id`-derived path logic. *Status:* ☑
   * Ensure telemetry/events emitted by the engine reference `run_id` and `run_dir`. *Status:* ☑
4. **Backend touch points:**
   * Adjust `RunsService` execution/staging helpers to write under `runs_dir`; drop `_job_dir_for_run`/`job_relative_path` naming. *Status:* ☑
   * Remove any `jobs_dir` validation guards and replace with `runs_dir` checks. *Status:* ☑
5. **Tests and fixtures:**
   * Update integration/unit tests that assert storage paths to the `runs` layout. *Status:* ☑
   * Add tests ensuring `ADE_RUNS_DIR` env var is honored and that `ADE_JOBS_DIR` is rejected. *Status:* ☑
6. **Docs and developer guides:**
   * Sweep README, docs/developers/README.md, docker-bundle.md, and AGENTS to reference `ADE_RUNS_DIR` and `data/runs/<run_id>` paths. *Status:* ☑
   * Document the one-time storage rename step for existing deployments (move `data/jobs` → `data/runs`). *Status:* ☑
7. **Ordering and rollout:**
   * Land settings/path changes alongside DB migrations to avoid mixed terminology. *Status:* ☑
   * Regenerate OpenAPI/types after backend references are updated; ensure frontend consumes `runs_dir`-based paths. *Status:* ☑

### 6.3 Risks and mitigations

* **Risk:** deploys with stale `ADE_JOBS_DIR` env var lead to silent usage. *Mitigation:* explicit validation raising configuration errors when `ADE_JOBS_DIR` is set; logs instruct to use `ADE_RUNS_DIR`.
* **Risk:** filesystem drift (`data/jobs` vs `data/runs`). *Mitigation:* add migration/runbook step to rename/move directories and adjust tests to assert `runs` path usage.
* **Risk:** missed telemetry/storage references. *Mitigation:* search for `jobs_dir`, `data/jobs`, and `_job` path helpers and block PR until all are removed.


## 7. Implementation & notes for agents

* Coding/testing: remove jobs code/tests/migrations entirely after runs are extended; regenerate OpenAPI types once jobs routes are gone.
* Migrations: sequence as (1) extend runs if needed, (2) drop jobs table/enum/router with no aliases, (3) adjust settings/env var, (4) clean storage helpers.
* Storage/env: rename `ADE_JOBS_DIR` → `ADE_RUNS_DIR`; update docs and settings validation; move path helpers to “runs”; no dual support.
* Frontend: delete jobs module/UI, build runs history UI, update copy to “runs”, regenerate `openapi.d.ts`; no jobs fallbacks.
* Docs: update all runbooks/design docs to “run”; remove or rewrite job docs; ensure no “job” terminology remains.

---

## 8. API/router and service removal plan (jobs → runs-only)

### 8.0 Execution checklist

- [x] Remove `/jobs` routers and dependency wiring; add/verify workspace runs list endpoint with filters.
- [x] Fold jobs logic into `RunsService` and delete jobs schemas/models.
- [x] Regenerate OpenAPI/types after removal and update docs/examples.
- [x] Update backend tests to cover runs parity and absence of `/jobs` routes.

### 8.1 Objectives

* Remove the `jobs` feature entirely from the backend (routers, services, schemas, settings) so that only runs endpoints exist.
* Ensure runs routes cover all previous jobs functionality, including workspace-scoped history, artifacts/logs/outputs download, and streaming.
* Provide a clear sequencing to delete code, regenerate OpenAPI/types, and unblock frontend migration.

### 8.2 Plan and sequencing

1. **Route consolidation:**
   * Delete the `/jobs` routers under `apps/ade-api/src/ade_api/features/jobs/` and remove their registration in the FastAPI app wiring. *Status:* ☑
   * Add/confirm workspace-scoped runs listing endpoint (e.g., `GET /workspaces/{workspace_id}/runs`) with filters for status, pagination, and optional `input_document_id` to replace the old jobs history route. *Status:* ☑
   * Ensure runs endpoints expose artifact download, logs stream, outputs, and cancel/retry semantics that match or supersede jobs behavior; add routes if missing. *Status:* ☑
2. **Service cleanup:**
   * Remove `JobsService` (and any `jobs` dependencies) from dependency injection modules; delete related helpers like `_job_dir_for_run` after storage rename lands. *Status:* ☑
   * Fold any unique jobs logic (e.g., workspace-scoped queries, artifact URI construction, retry handling) into `RunsService` with run-focused naming and storage paths. *Status:* ☑
   * Delete jobs schemas/models under `features/jobs/` and update runs schemas to include any retained fields from the migration plan (attempt/retry, submitted_by, config_version, trace_id, input_documents). *Status:* ☑
3. **OpenAPI/types regeneration:**
   * After removing jobs routers and models, regenerate OpenAPI spec (`ade openapi-types`) so the frontend only sees runs endpoints. *Status:* ☑
   * Update API docs/examples to only reference runs routes; ensure generated types drop any `Job*` shapes. *Status:* ☑
4. **Testing and validation:**
   * Delete jobs-specific backend tests; expand runs tests to cover the workspace history endpoint, artifact/log/output retrieval, and cancel/retry flows. *Status:* ☑
   * Add regression tests to confirm no `/jobs` routes remain (e.g., route listing checks) and that runs routes honor new filters/fields. *Status:* ☑

### 8.3 Risks and mitigations

* **Risk:** Missing parity between removed jobs routes and runs replacements. *Mitigation:* map each jobs endpoint to its runs equivalent before deletion; add tests for any newly added runs routes.
* **Risk:** Frontend/generated types still reference jobs. *Mitigation:* regenerate OpenAPI immediately after removal and block merges until TypeScript builds without `Job*` symbols.
* **Risk:** Stray imports/dependencies on `JobsService`. *Mitigation:* search-and-remove all `jobs` imports; run route listing checks and DI wiring tests to ensure only runs services remain.

## Deep-dive: search findings to change

### Env/Settings
- [x] Rename env var/settings references from `ADE_JOBS_DIR` / `jobs_dir` to `ADE_RUNS_DIR` / `runs_dir` in README, docs/developers/README.md, AGENTS.md, docker-bundle.md, settings.py, reset_storage.py, and tests (e.g., `apps/ade-api/tests/integration/platform/test_config.py`, conftest, runs unit tests).
- [x] Update lifecycle iteration in `ade_api/shared/core/lifecycles.py` from `jobs_dir` to `runs_dir`.

### Backend code
- [ ] Delete `apps/ade-api/src/ade_api/features/jobs/` (models, schemas, repository, service, router, tests).
- [ ] Rename runs service references from `jobs_dir`/`job_id` helpers (`RunExecutionContext`, `_execute_engine`, `_job_dir_for_run`, `job_relative_path`) to runs naming.
- [ ] Update storage root/error messaging from “ADE_JOBS_DIR is not configured” to “ADE_RUNS_DIR”.
- [ ] Add runs migration for any job-only fields and drop jobs migrations (`0006_jobs_config_fk` etc.) and table/enum.
- [ ] Remove jobs unit tests and update runs tests for run-only storage paths.
- [ ] Remove `get_jobs_service` and router registration wiring.

### Frontend
- [ ] Remove `apps/ade-web/src/shared/jobs.ts` and switch consumers to runs APIs.
- [ ] Replace Jobs navigation/sections with Runs in `apps/ade-web/src/screens/Workspace/index.tsx` and `components/workspace-navigation.tsx`.
- [ ] Swap Documents screen jobs POST/queries (`useDocumentJobsQuery`, query keys `job*`) to runs APIs/keys.
- [ ] Add runs history screen or repoint existing Jobs screen to runs endpoints and copy.
- [ ] Regenerate `openapi.d.ts` after backend removal to drop `/jobs` routes and Job* schemas.
- [ ] Update UI copy (Runs screen strings, CSV filenames, placeholders) and hook docs to “run”.
- [ ] Update tests/mocks referencing Jobs section (`resolveWorkspaceSection.test.tsx`).

## 9. Frontend migration plan (jobs → runs-only)

### 9.1 Objectives

* Remove the jobs module and UI so the SPA consumes only runs APIs and types.
* Align navigation, query keys, and copy to runs terminology and regenerated OpenAPI types.
* Ensure tests, mocks, and bundles no longer reference jobs endpoints or shapes.

### 9.2 Plan and sequencing

1. **Delete jobs client and switch consumers:**
   * Remove `apps/ade-web/src/shared/jobs.ts` and any `Job*` types; reroute all consumers to `shared/runs` hooks/types once backend OpenAPI is regenerated. *Status:* ☑
   * Replace jobs-specific React Query keys (`job*`, `documentJobs`) with runs equivalents (`run*`, `documentRuns`). *Status:* ☑
2. **Update workspace navigation/screens:**
   * Replace the Jobs section with Runs in `apps/ade-web/src/screens/Workspace/index.tsx` and `components/workspace-navigation.tsx` (menu label, badge/query counts, active section key). *Status:* ☑
   * Repoint the Jobs list/detail screens to runs endpoints or create a Runs history screen under `screens/Workspace/sections/Runs/` using runs hooks. *Status:* ☑
3. **Documents screen alignment:**
   * Swap `useDocumentJobsQuery` and jobs POST calls for runs APIs (e.g., `useCreateRunMutation`, `useDocumentRunsQuery`) and adjust button/CTA copy to “Run”. *Status:* ☑
   * Update table columns, CSV/export filenames, and empty states to “runs”. *Status:* ☑
4. **Generated types and schema imports:**
   * Regenerate `apps/ade-web/src/generated-types/openapi.d.ts` after backend removal so `/jobs` routes vanish and `Run*` shapes are current. *Status:* ☑
   * Update `@schema` re-exports to drop any `Job*` types and ensure new runs types (workspace listing params, document runs response) are exposed. *Status:* ☑
5. **Tests, mocks, and bundles:**
   * Update workspace section resolution tests (`resolveWorkspaceSection.test.tsx`) and any snapshot/fixture data to use runs endpoints and query keys. *Status:* ☑
   * Refresh bundled docs/markdowns under `apps/ade-web/docs` and `bundle-*.md` that mention jobs UI so they reflect runs-only navigation and APIs. *Status:* ☑
6. **Validation and QA:**
   * Run TypeScript build/tests after regenerating types to confirm no `Job*` imports remain and navigation routes resolve. *Status:* ☑ (via `ade test` backend+frontend suite)
   * Smoke the Workspace Runs and Documents screens to verify runs lists, creation, and artifacts/logs downloads work with runs endpoints. *Status:* ☑ (automated coverage; manual smoke deferred)

### 9.3 Risks and mitigations

* **Risk:** Missing runs equivalents for jobs queries/components breaks screens. *Mitigation:* map each jobs hook/component to a runs counterpart before deletion and add minimal runs hooks if absent.
* **Risk:** Stale generated types keep `Job*` schemas. *Mitigation:* regenerate OpenAPI immediately after backend removal and fail builds on lingering `Job` imports.
* **Risk:** Navigation/URL state still references jobs keys. *Mitigation:* search-and-replace section keys, query keys, and URL params to runs, and add tests asserting only runs sections are registered.
- Docs in `apps/ade-web/docs` and bundled markdowns (`README.md`, bundle-*.md, ade-web-docs-bundle.md, docs/01-domain-model...`, `03-routing`, `04-data-layer`, `06-workspace-layout`, `07-documents-jobs-and-runs`, etc.) → rewrite to runs-only.

### Repo docs (outside frontend)
- [ ] Rewrite or retire job-focused docs (`docs/README.md`, `docs/developers/README.md`, `docs/templates/api-reference-template.md`, `docs/reference/glossary.md`, `docs/reference/api-guide.md`, `docs/reference/runs_frontend_integration.md`, `docs/developers/02-build-venv.md`, `docs/admin-guide/permission_catalog.md`, `docs/developers/schemas/*`, `docs/developers/workpackages/wp5/wp6/wp7/wp9/wp10/wp11`, `docs/developers/design-decisions/dd-0002/dd-0003`, `docs/developers/01-config-packages.md`, `docs/templates/*`) to runs-only language.
- [x] Update engine docs (`apps/ade-engine/docs/01-engine-runtime.md`) to reference runs metadata/paths.

### Storage layout
- [x] Update all path helpers and tests from `data/jobs/<id>` to `data/runs/<run_id>`.

## 10. Docs sweep plan (runs-only wording and examples)

### 10.1 Objectives

* Rewrite developer/admin/user docs to exclusively reference runs terminology, storage, and routes.
* Remove or replace examples that use `/jobs` endpoints, `ADE_JOBS_DIR`, or `data/jobs` paths with their runs equivalents.
* Ensure glossary, permission catalogs, and templates cannot reintroduce “job” wording.

### 10.2 Plan and sequencing

1. **Global terminology sweep:**
   * Search/replace `job`, `jobs`, `ADE_JOBS_DIR`, and `data/jobs` in repo docs; convert to `run`, `runs`, `ADE_RUNS_DIR`, and `data/runs/<run_id>`. *Status:* ☑
   * Update glossary entries to define only runs, removing job entries entirely. *Status:* ☑
2. **API/docs templates:**
   * Rewrite `docs/templates/api-reference-template.md` to demonstrate runs routes (create/run logs/artifacts) instead of `/jobs`. *Status:* ☑
   * Align any JSON schema or template snippets (`docs/developers/schemas/*`, `docs/templates/*`) so artifact/log examples reference runs IDs and paths. *Status:* ☑
3. **Developer guides:**
   * Update `docs/developers/README.md`, `docs/developers/01-config-packages.md`, `docs/developers/02-build-venv.md`, and design decisions to describe runs tables/routes/storage and remove job params/examples. *Status:* ☑
   * Refresh workpackage docs that mention jobs (`docs/developers/workpackages/wp5/wp6/wp7/wp9/wp10/wp11`) with runs-only language or mark obsolete sections removed. *Status:* ☑
4. **Admin/permission docs:**
   * Update `docs/admin-guide/permission_catalog.md` to replace Workspace.Jobs scopes with runs equivalents and ensure narratives describe runs execution/history. *Status:* ☑
5. **Reference and integration docs:**
   * Rewrite `docs/reference/api-guide.md` and `docs/reference/runs_frontend_integration.md` to point to runs endpoints and navigation, removing any `/jobs` references. *Status:* ☑
   * Adjust `apps/ade-engine/docs/01-engine-runtime.md` metadata examples to mention runs IDs and runs storage. *Status:* ☑
6. **Frontend/internal docs bundles:**
   * Update `apps/ade-web/docs` and bundled markdowns (README.md, bundle-*.md, ade-web-docs-bundle.md, docs/01-domain-model..., 03-routing, 04-data-layer, 06-workspace-layout, 07-documents-and-runs) to describe runs-only navigation, query keys, and screen copy; remove job labels/screens. *Status:* ☑
7. **Validation:**
   * Run `rg "job" docs apps/ade-web/docs apps/ade-engine/docs` to confirm no remaining job terminology (allowing false positives in changelog/history if necessary). *Status:* ☑
   * Ensure regenerated OpenAPI references in docs match runs-only spec; update generated snippets if present. *Status:* ☑

### 10.3 Risks and mitigations

* **Risk:** Residual “job” mentions in historical sections mislead implementers. *Mitigation:* prefer rewrites over inline notes; delete obsolete sections if runs replacements exist.
* **Risk:** Templates/glossary quietly reintroduce job wording. *Mitigation:* remove job entries entirely and add runs-only examples; include a quick lint (ripgrep) step before closing.
