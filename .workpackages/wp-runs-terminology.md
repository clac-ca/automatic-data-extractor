# Work Package: Replace "jobs" with "runs" across ADE

## Work Package Checklist

- [ ] Finalize target terminology and scope (runs-only, zero “job” remnants) across backend, frontend, docs, settings
- [ ] Plan DB/schema migration: extend runs if needed; drop jobs tables/enums/migrations
- [ ] Plan storage/env rename to ADE_RUNS_DIR and path layout `data/runs/<run_id>/...`
- [ ] Plan API/router and service removals (delete jobs feature; runs endpoints cover all)
- [ ] Plan frontend migration (remove jobs module/UI; runs-only); regenerate OpenAPI types
- [ ] Plan docs sweep to remove “job(s)” and align run terminology and examples

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

## 5. Implementation & notes for agents

* Coding/testing: remove jobs code/tests/migrations entirely after runs are extended; regenerate OpenAPI types once jobs routes are gone.
* Migrations: sequence as (1) extend runs if needed, (2) drop jobs table/enum/router with no aliases, (3) adjust settings/env var, (4) clean storage helpers.
* Storage/env: rename `ADE_JOBS_DIR` → `ADE_RUNS_DIR`; update docs and settings validation; move path helpers to “runs”; no dual support.
* Frontend: delete jobs module/UI, build runs history UI, update copy to “runs”, regenerate `openapi.d.ts`; no jobs fallbacks.
* Docs: update all runbooks/design docs to “run”; remove or rewrite job docs; ensure no “job” terminology remains.

---

## Deep-dive: search findings to change

### Env/Settings
- Env var `ADE_JOBS_DIR` and `jobs_dir` settings in README, docs/developers/README.md, AGENTS.md, docker-bundle.md, settings.py, reset_storage.py, tests (`apps/ade-api/tests/integration/platform/test_config.py`, conftest, runs unit tests) → rename to `ADE_RUNS_DIR` / `runs_dir`.
- Lifecycles: `ade_api/shared/core/lifecycles.py` iterates `jobs_dir` → update.

### Backend code
- Delete `apps/ade-api/src/ade_api/features/jobs/` (models, schemas, repository, service, router, tests).
- Runs service still references `jobs_dir` and job_id overrides (`RunExecutionContext` fields, `_execute_engine`, path helpers `_job_dir_for_run`, `job_relative_path`) → rename to runs and drop `job_id`.
- Storage root and errors: “ADE_JOBS_DIR is not configured” → “ADE_RUNS_DIR”.
- Migrations: add runs migration for any job-only fields; drop jobs migrations (`0006_jobs_config_fk` etc.) and table/enum.
- Tests: remove jobs unit tests; update runs tests for run-only storage paths.
- Dependency wiring: remove get_jobs_service and router registration.

### Frontend
- Remove `apps/ade-web/src/shared/jobs.ts`; switch consumers to runs APIs.
- Workspace navigation/sections: replace Jobs section with Runs; update `Workspace/index.tsx` and `components/workspace-navigation.tsx`.
- Documents screen uses jobs POST/queries (`useDocumentJobsQuery`, query keys `job*`) → swap to runs APIs and keys.
- Runs UI: add runs history screen or repoint existing Jobs screen to runs endpoints and copy.
- Generated types: `openapi.d.ts` includes `/jobs` routes and Job* schemas → regenerate after backend removal.
- UI copy: “jobs” strings in Runs screen, CSV filenames, placeholder text; code editor hook doc strings referencing “job” → align to “run”.
- Tests/mocks referencing Jobs section (`resolveWorkspaceSection.test.tsx`).
- Docs in `apps/ade-web/docs` and bundled markdowns (`README.md`, bundle-*.md, ade-web-docs-bundle.md, docs/01-domain-model...`, `03-routing`, `04-data-layer`, `06-workspace-layout`, `07-documents-jobs-and-runs`, etc.) → rewrite to runs-only.

### Repo docs (outside frontend)
- Job-focused docs to rewrite or retire: `docs/README.md` (“jobs run”, “monitoring jobs”), `docs/developers/README.md` (numerous job mentions, paths, tables, hook names), `docs/templates/api-reference-template.md` (POST /jobs template), `docs/reference/glossary.md` (job definition), `docs/reference/api-guide.md` (jobs routes), `docs/reference/runs_frontend_integration.md` (calls out legacy jobs endpoints), `docs/developers/02-build-venv.md` (job language and tables), `docs/admin-guide/permission_catalog.md` (Workspace.Jobs scopes), `docs/developers/schemas/*` (artifact schema job node), `docs/developers/workpackages/wp5/wp6/wp7/wp9/wp10/wp11` (job terminology), `docs/developers/design-decisions/dd-0002/dd-0003`, `docs/developers/01-config-packages.md` (job params in hooks), `docs/templates` references. Rewrite to runs-only or delete obsolete sections.
- Engine docs: `apps/ade-engine/docs/01-engine-runtime.md` mentions “backend jobs” metadata → update to runs wording if keeping metadata examples.

### Storage layout
- All path helpers and tests assume `data/jobs/<id>`: update runs service and callers to `data/runs/<run_id>`.
