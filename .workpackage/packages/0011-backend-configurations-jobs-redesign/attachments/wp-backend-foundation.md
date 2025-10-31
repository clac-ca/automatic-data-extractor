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
  - [ ] Extend migration 0001 with tables for configs, config_versions, workspace_config_states, and jobs (including artifact + normalized outputs paths).
  - [ ] Implement SQLAlchemy models mirroring schema relationships and soft-delete/archival flags.
  - [ ] Ensure lifecycle bootstraps configs and jobs directories beneath `ADE_STORAGE_DATA_DIR` on startup.
  - [ ] Add tests asserting tables exist, relationships enforce single active version per workspace, and directories are created.

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
  - [ ] Add storage helper for config package layout and hashing of manifest + code files.
  - [ ] Implement repository/service methods for create/import, list/detail, version publish, activation, and archive/unarchive flows.
  - [ ] Expose FastAPI router with endpoints for package CRUD, version history, activation, and export/import payloads.
  - [ ] Cover API behavior with tests for manifest validation, workspace activation, archive restrictions, and error envelopes.

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
  - [ ] Define repository/service/orchestrator coordinating queue, subprocess launch, and state transitions.
  - [ ] Materialize job run directories with input copy, config snapshot, artifact + normalized placeholders, and optional vendor deps.
  - [ ] Implement synchronous pass runner stub that respects manifest hooks and writes artifact + normalized outputs.
  - [ ] Add API tests verifying submission throttling, state changes, artifact paths, and diagnostics payloads.

---

These work packages lay the groundwork for sandboxing/resource limits, diagnostics surfacing, and workspace UX improvements documented in the research findings.
