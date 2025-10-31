# ADE Backend Foundation Work Packages

## Overview
These staged work packages translate the config package and job orchestration design docs into incremental backend milestones. Each phase builds toward the single-active-config model, manifest-driven package layout, and multi-pass job runner described in `docs/developers/README.md`, `01-config-packages.md`, and `02-job-orchestration.md`.

---

## WP1 — Metadata & Storage Baseline
- **Goals:** Create durable metadata tables for configs, config versions, workspace activation state, and jobs. Establish deterministic on-disk layout for config packages and per-job artifacts under `ADE_STORAGE_DATA_DIR`.
- **Deliverables:** Updated Alembic migration, SQLAlchemy models, and startup bootstrap that provision package and job directories.
- **Code:** `backend/app/shared/db/migrations/versions/0001_initial_schema.py`, `backend/app/features/configs/models.py`, `backend/app/features/jobs/models.py`, `backend/app/shared/core/lifecycles.py`.
- **Testing:** Unit tests confirming new tables exist, models reflect schema, and runtime directories are created for configs and jobs beneath `ADE_STORAGE_DATA_DIR` (for example `data/configs/<config_id>/<version>/` and `data/jobs/<job_id>/`).
- **Acceptance:**
  - Schema stores config metadata, version manifest JSON + content hashes, workspace → active_version mapping, and job lifecycle fields (queued/started/completed timestamps, artifact paths).
  - Startup bootstrap ensures config + job storage roots exist with correct permissions.
- **Checklist:**
- [x] Extend migration 0001 with tables for configs, config_versions, workspace_config_states, and jobs (including artifact + normalized outputs paths).
- [x] Implement SQLAlchemy models mirroring schema relationships and soft-delete/archival flags.
- [x] Ensure lifecycle bootstraps configs and jobs directories beneath `ADE_STORAGE_DATA_DIR` on startup.
- [x] Add tests asserting tables exist, relationships enforce single active version per workspace, and directories are created.

## WP2 — Config Registry & Package Lifecycle
- **Goals:** Implement services that manage manifest-backed config packages on disk, enforce single active config per workspace, and expose FastAPI endpoints for CRUD/version operations.
- **Deliverables:** Config repository/service/router, storage helpers that materialize package structure (`manifest.json`, `columns/`, `row_types/`, `hooks/`, optional `requirements.txt`), and manifest validation aligned with docs.
- **Code:** `backend/app/features/configs/{repository.py,service.py,schemas.py,router.py}`, storage helpers under `backend/app/features/configs/storage.py`, shared manifest validation utilities.
- **Testing:** API + service tests covering create/import, versioning with immutable hashes, workspace activation semantics, and manifest validation errors.
- **Acceptance:**
  - Config creation records metadata + version row, materializes package folder, and validates manifest/structure against doc contracts.
  - Workspace activation flips active version while keeping prior versions immutable; archived configs remain read-only.
  - Routes surface list/detail/version activation + download/upload of package zips.
- **Checklist:**
- [x] Add storage helper for config package layout and hashing of manifest + code files.
- [x] Implement repository/service methods for create/import, list/detail, version publish, activation, and archive/unarchive flows.
- [x] Expose FastAPI router with endpoints for package CRUD, version history, activation, and export/import payloads.
- [x] Cover API behavior with tests for manifest validation, workspace activation, archive restrictions, and error envelopes.

## WP3 — Job Orchestration Skeleton
- **Goals:** Provide a minimal job manager that queues work, prepares sandbox-ready working directories, runs the documented pass pipeline, and persists artifacts/output metadata.
- **Deliverables:** Job repository/service/orchestrator modules, router endpoints for submit/list/detail, helpers to emit `artifact.json` and streaming `normalized.xlsx`, and a subprocess adapter stub (no resource limits yet).
- **Code:** `backend/app/features/jobs/{repository.py,service.py,schemas.py,router.py,orchestrator.py}`, shared sandbox utilities under `backend/app/shared/adapters/` as needed.
- **Testing:** Service and API tests verifying queueing, status transitions (QUEUED → RUNNING → SUCCEEDED/FAILED), artifact + normalized file creation, and recorded pass diagnostics.
- **Acceptance:**
  - Submitting a job enqueues it, materializes `var/jobs/<job_id>/` (input copy, config snapshot, vendor dir), and launches pass runner in an isolated subprocess per design recommendation.
  - Pass pipeline appends to artifact JSON in order (detect → map → transform → validate → output) and records diagnostics for UI.
  - Job records persist artifact/normalized paths, runtime stats, and failure diagnostics on error.
- **Checklist:**
- [x] Define repository/service/orchestrator coordinating queue, subprocess launch, and state transitions.
- [x] Materialize job run directories with input copy, config snapshot, artifact + normalized placeholders, and optional vendor deps.
- [x] Implement synchronous pass runner stub that respects manifest hooks and writes artifact + normalized outputs.
- [x] Add API tests verifying submission throttling, state changes, artifact paths, and diagnostics payloads.

---

## WP4 — Config Authoring Surface (Manifest + Files API)
- **Goals:** Support granular editing of config packages directly from the new frontend experience without full ZIP round-trips.
- **Deliverables:** Endpoints to list package trees, stream individual files, update manifest metadata, and save script modules; change tracking helpers for drafts; upload/download parity.
- **Code:** `backend/app/features/configs/{router.py,service.py,storage.py}`, potential helpers under `backend/app/features/configs/editor.py`.
- **Testing:** API tests for file CRUD, optimistic lock/version conflicts, diff previews, and ZIP reconstruction; storage tests ensuring canonical archives stay intact.
- **Acceptance:**
  - Clients can fetch manifest JSON and package files individually, edit them, and persist changes to a new version.
  - Package exports reflect on-disk edits and continue to validate via the manifest schema and dynamic validator.
  - Archive/immediate activation rules still enforce single active config per workspace.
- **Checklist:**
- [x] Extend storage layer with read/write helpers for manifest and module files (respecting vendor + requirements layout).
- [x] Add router endpoints for `GET/PUT /files/{path}` and manifest metadata patching with CSRF + workspace auth.
- [x] Implement draft work-in-progress support (temp directories or version staging) with conflict detection.
- [x] Provide download endpoints for manifest JSON and full package ZIP (including optional vendor dir).
- [x] Cover validation + export flows with API tests and ensure existing create/publish paths reuse the same helpers.

## WP5 — Runtime Execution Parity with Design Docs
- **Goals:** Replace the worker stub with the full pass pipeline described in `02-job-orchestration.md`, using the script API defined in `01-config-packages.md`.
- **Deliverables:** Streaming reader for XLSX inputs, manifest-driven pass runner that loads detectors/transforms/validators, hook invocation, artifact writer respecting schema.
- **Code:** `backend/app/features/jobs/worker.py`, shared helpers under `backend/app/features/jobs/runtime/`, potential refactors in `backend/app/features/jobs/orchestrator.py`.
- **Testing:** Unit tests for each pass, integration tests asserting artifact content matches expectations, regression suite using sample config packages.
- **Acceptance:**
  - Worker reads input spreadsheets, runs find→map→transform→validate→output passes, and records results per artifact spec (`docs/developers/14-job_artifact_json.md`).
  - Hooks declared in manifest run with sandboxed context; failures surface as diagnostics and halt pipeline per design.
  - Artifact + normalized outputs include real data derived from the input file; mapping scores and issues align with script return contracts.
- **Checklist:**
- [x] Implement Excel streaming reader with support for manifest sampling knobs (row/column sampling).
- [x] Load row/column modules dynamically from the stored package, honoring vendor dependencies and `config_script_api_version`.
- [x] Execute passes sequentially, accumulating diagnostics and writing artifact sections documented in `02-job-orchestration.md`.
- [x] Respect hook ordering (`on_job_start`, `after_mapping`, `after_transform`, `after_validate`, etc.) and propagate errors.
- [x] Update worker result payload to include detailed diagnostics, timing, and failure metadata for the Jobs API.

## WP6 — Job Input Handling & Document Integration
- **Goals:** Bridge document storage with job execution so real user uploads become job inputs with idempotent hashing.
- **Deliverables:** Repository/service updates to resolve document binaries, copy them into job directories, and persist run metadata; optional preflight validation for unsupported formats.
- **Code:** `backend/app/features/jobs/{service.py,storage.py}`, `backend/app/features/documents/`, potential shared utilities under `backend/app/shared/io/`.
- **Testing:** Service tests that submit jobs with documents, ensure inputs are staged, and hashed for idempotency; API tests covering retries and unsupported file errors.
- **Acceptance:**
  - Jobs API accepts document references (or direct file uploads) and materializes `input.xlsx` in the job folder.
  - Idempotency key uses a stable hash of the document + config version; retries reuse prior outputs when applicable.
  - Validation rejects non-supported file types gracefully with actionable error messages.
- **Checklist:**
- [x] Implement document resolution + copy into `JobsStorage.prepare()` (supporting large file streaming).
- [x] Update `JobsService._resolve_inputs` to fetch documents and compute hashes prior to enqueue.
- [x] Ensure job directory clean-up retains artifacts while optionally purging temporary inputs per retention policy.
- [x] Add tests for duplicate submissions, missing documents, and multi-file jobs (if supported by future design).

## WP7 — Observability, Cancellation, and Hardening
- **Goals:** Align with future hardening notes in `02-job-orchestration.md` by adding cancel support, improved logging/metrics, and stricter sandboxing.
- **Deliverables:** Cancel endpoint, process group kill logic, structured logs/metrics hooks, optional seccomp/bubblewrap integration flag.
- **Code:** `backend/app/features/jobs/{router.py,service.py,orchestrator.py}`, shared adapters under `backend/app/shared/observability/`.
- **Testing:** Tests asserting cancel transitions, worker termination behavior, and metric emission; stress tests for queue overflow.
- **Acceptance:**
  - Users can cancel queued or running jobs; subprocesses terminate cleanly and mark status `cancelled`.
  - Logs capture structured events, integrate with existing `events.ndjson`, and surface into diagnostics on failure.
  - Resource limit configuration is validated on startup with sensible defaults and override guards.
- **Checklist:**
- [ ] Introduce cancel API + service orchestration (including safe termination + cleanup).
- [ ] Emit structured metrics/events for job lifecycle (queued, running, succeeded, failed, cancelled).
- [ ] Add configuration validation + documentation updates for new environment knobs (timeouts, memory, sandbox options).
- [ ] Evaluate sandbox hardening options (process groups, seccomp, drop privileges) and implement baseline.

## WP8 — Secrets & Environment Management
- **Goals:** Provide a secure secrets store and runtime injection path that matches the manifest contracts in `01-config-packages.md` and the safety guidance in `docs/developers/README.md`.
- **Deliverables:** Encrypted-at-rest secrets storage, CRUD APIs for config-level secrets, integration with manifest `env` overrides and job sandbox environment.
- **Code:** `backend/app/features/configs/{schemas.py,service.py,router.py}`, `backend/app/shared/security/`, potential Alembic migrations for secrets tables.
- **Testing:** API tests covering secret creation/update/audit, permission checks, and redaction; worker tests ensuring secrets surface via `env` but never leak into artifacts/logs.
- **Acceptance:**
  - Secrets are stored encrypted, scoped per workspace/config, and versioned for audit.
  - Jobs receive decrypted secrets through the subprocess environment only when the manifest requests them.
  - Secrets never appear in stored manifests, artifacts, or job logs; misuse triggers validation diagnostics.
- **Checklist:**
  - [ ] Add secrets table/model with encryption + audit columns (created_by, last_used, etc.).
  - [ ] Extend configs router/service with secret CRUD endpoints and permission guards.
  - [ ] Update manifest validation to ensure secret references are declared and sanitized.
  - [ ] Inject secrets into worker environment and redact from diagnostics/log exports.
  - [ ] Document operational handling in `docs/developers/README.md` and security appendix.

## WP9 — API Surface & Contract Automation
- **Goals:** Lock down backend contracts for the new frontend by providing OpenAPI stability, generated TypeScript types, and regression coverage for error envelopes.
- **Deliverables:** Hardened FastAPI routes with explicit schemas, `npm run openapi-typescript` automation, CI check for contract drift, and comprehensive API tests for configs/jobs flows.
- **Code:** `backend/app/api/v1/__init__.py`, `backend/app/features/{configs,jobs}/schemas.py`, automation under `scripts/` and `package.json`.
- **Testing:** Snapshot tests for OpenAPI output, contract tests verifying response shapes, frontend type generation smoke test.
- **Acceptance:**
  - OpenAPI spec reflects all config/job endpoints and stays backward compatible across releases.
  - Frontend obtains generated types (via `npm run openapi-typescript`) wired into the CI pipeline.
  - Error envelopes are consistent (message + optional diagnostics) across validation, archive, and runtime failures.
- **Checklist:**
  - [ ] Audit and finalize Pydantic response models for every config/job route.
  - [ ] Add OpenAPI generation script + CI guard diffing committed spec.
  - [ ] Extend API tests to cover negative paths (manifest mismatch, invalid secrets, job timeouts).
  - [ ] Publish updated REST documentation in `docs/developers/README.md` or a dedicated API page.

## WP10 — Deployment & Ops Readiness
- **Goals:** Ensure the service is production-ready with configuration knobs, migrations, data retention, and operational docs.
- **Deliverables:** Environment variable documentation, bootstrap scripts, data retention policies for job artifacts/configs, and observability dashboards.
- **Code:** `backend/app/shared/core/config.py`, deployment manifests, `docs/developers/` ops guides.
- **Testing:** Smoke tests for configuration loading, migration verification in CI, scripted backups/cleanup dry runs.
- **Acceptance:**
  - Application boots cleanly with documented environment variables (storage dirs, secrets backend, concurrency limits).
  - Scheduled cleanup removes stale job directories while respecting retention requirements.
  - Deployment playbook covers database migrations, initial admin provisioning, secrets rotation, and rollback strategy.
- **Checklist:**
  - [ ] Expand settings model with validation + defaults for new features (queues, secrets, storage).
  - [ ] Provide Alembic migration management docs and automated checks (`npm run ci`).
  - [ ] Implement artifact retention worker or CLI to prune old jobs/config versions safely.
  - [ ] Document deployment + recovery procedures, including scaling guidance and monitoring alerts.

---

These work packages lay the groundwork for sandboxing/resource limits, diagnostics surfacing, and workspace UX improvements documented in the research findings.
