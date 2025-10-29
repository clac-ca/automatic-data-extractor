# Implementation Checklist — Config Engine v0.4

Status legend: `[ ]` todo • `[~]` in progress • `[x]` done

---

## Phase 0 — Archive & prep
- [ ] Create branch `feat/configs-filesystem-simplify`.
- [ ] `git mv backend/app/features/configurations backend/app/features/_legacy_configurations`.
- [ ] Verify Alembic/env imports no longer pull the legacy package.
- [ ] Commit archive snapshot (`chore(configs): archive legacy configurations feature`).
- [ ] Capture current workspace→active configuration mapping for optional migration script.

## Phase 1 — Schema & migration
- [ ] Add SQLAlchemy model `Config` + `ConfigStatus` enum in `backend/app/features/configs/models.py`.
- [ ] Add `configs` table (ULID PK, status, created_by, timestamps, archived_at).
- [ ] Add `workspaces.active_config_id` FK.
- [ ] Create partial unique index enforcing one `active` per workspace.
- [ ] Drop legacy configuration/version/script tables.
- [ ] Update Alembic env to import new models.
- [ ] Implement Alembic revision `configs: flatten to file-backed design` (create tables/columns, optional data migration, drop legacy tables).

## Phase 2 — Storage & settings
- [ ] Add settings for `ADE_STORAGE_CONFIGS_DIR` and `ADE_SECRET_KEY`; document defaults in `.env.example`.
- [ ] Implement filesystem adapter rooted at the configs directory (list/write/delete/copy, fsync-safe).
- [ ] Compute deterministic folder hashes (sorted file SHA-256 concat → overall SHA-256).

## Phase 3 — Template & helpers
- [ ] Add `backend/app/features/configs/templates/default_config/` scaffold (manifest, hooks, two column modules, README).
- [ ] Implement `files.py` helpers (resolve paths, load/save manifest, list relative files, safe rename, import/export zip).
- [ ] Provide clone/import/export utilities that reuse helper logic.

## Phase 4 — Manifest, secrets, validation
- [ ] Define Pydantic schemas (`ConfigRecord`, `ConfigCreate/Update`, `Manifest`, `ValidationIssue`, `FileItem`).
- [ ] Implement AES-GCM helpers (`encrypt_secret`, `decrypt_secret`) using `ADE_SECRET_KEY`.
- [ ] Build `validation.py`: structure checks, manifest schema enforcement, module introspection (detect_* + transform), forbidden import lint, diagnostics formatting.
- [ ] Add CLI hook or management command to run validation locally (optional).

## Phase 5 — Service layer
- [ ] Implement `service.py` orchestration:
  - [ ] `create_config`, `clone_config`, `import_config`, `delete_config`, `archive_config`, `activate_config`, `list_configs`, `get_config`, `update_config`.
  - [ ] `get_manifest`, `put_manifest`, `list_files`, `read_file`, `write_file`, `delete_file`, `rename_column`, `export_config`.
  - [ ] `validate_config` (wraps validation module or delegates to jobs validation hook).
- [ ] Ensure services keep `workspaces.active_config_id` and `configs.status` consistent and handle hook failures (rollback activation).
- [ ] Expose diagnostics and hash metadata for API responses.

## Phase 6 — API & exceptions
- [ ] Define domain exceptions (not found, conflict, bad request, activation failure, manifest invalid, file errors).
- [ ] Implement FastAPI router (`router.py`) with endpoints:
  - [ ] CRUD + activation.
  - [ ] Manifest GET/PUT.
  - [ ] Files list/read/write/delete + rename.
  - [ ] Import/export.
  - [ ] Validate.
- [ ] Register router in `backend/app/api/v1/__init__.py`; remove legacy `/configurations/**` routes.
- [ ] Map exceptions to HTTP responses (404, 409, 400, 412, 500).

## Phase 7 — Jobs integration touchpoints
- [ ] Update job submission to resolve `workspaces.active_config_id` by default (allow override later).
- [ ] Ensure the jobs feature loads config folder paths from the storage adapter and owns sandbox execution.
- [ ] Surface any validation hooks needed so jobs can refuse malformed configs before activation.
- [ ] Guard against executing archived configs (enforce in jobs service).

## Phase 8 — Tests & QA
- [ ] Unit tests for storage helpers, manifest parser, crypto utilities, validation rules.
- [ ] API tests covering CRUD, activation, manifest/file mutations, import/export, validation errors.
- [ ] End-to-end smoke: create from template → write detector → validate → activate (run `on_activate`) → ensure active pointer updated.
- [ ] Regression checks that secrets remain encrypted at rest and never logged.

## Phase 9 — Documentation & cleanup
- [ ] Update README/AGENTS/developer docs with new workflow, settings, and API references.
- [ ] Add ADR summarizing the file-backed design and deprecation of legacy versions.
- [ ] Remove remaining references to `_legacy_configurations` once frontend migrates.
- [ ] Communicate cutover plan + rollback steps to stakeholders.
